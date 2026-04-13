import os
import hashlib
import hmac
import base64
import json
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import urllib.request
from datetime import datetime, timedelta, date

# ─── 環境変数 ──────────────────────────────────────────────────
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OWNER_USER_ID = os.environ.get("OWNER_LINE_USER_ID", "")

LINE_REPLY_API = "https://api.line.me/v2/bot/message/reply"
LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"

# ─── 西洋占星術（星座テーブル）──────────────────────────────────
ZODIAC_SIGNS = [
    {"sign": "山羊座", "symbol": "♑", "element": "地", "ruler": "土星",
     "start": (12, 22), "end": (1, 19)},
    {"sign": "水瓶座", "symbol": "♒", "element": "風", "ruler": "天王星",
     "start": (1, 20), "end": (2, 18)},
    {"sign": "魚座", "symbol": "♓", "element": "水", "ruler": "海王星",
     "start": (2, 19), "end": (3, 20)},
    {"sign": "牡羊座", "symbol": "♈", "element": "火", "ruler": "火星",
     "start": (3, 21), "end": (4, 19)},
    {"sign": "牡牛座", "symbol": "♉", "element": "地", "ruler": "金星",
     "start": (4, 20), "end": (5, 20)},
    {"sign": "双子座", "symbol": "♊", "element": "風", "ruler": "水星",
     "start": (5, 21), "end": (6, 21)},
    {"sign": "蟹座", "symbol": "♋", "element": "水", "ruler": "月",
     "start": (6, 22), "end": (7, 22)},
    {"sign": "獅子座", "symbol": "♌", "element": "火", "ruler": "太陽",
     "start": (7, 23), "end": (8, 22)},
    {"sign": "乙女座", "symbol": "♍", "element": "地", "ruler": "水星",
     "start": (8, 23), "end": (9, 22)},
    {"sign": "天秤座", "symbol": "♎", "element": "風", "ruler": "金星",
     "start": (9, 23), "end": (10, 23)},
    {"sign": "蠍座", "symbol": "♏", "element": "水", "ruler": "冥王星",
     "start": (10, 24), "end": (11, 22)},
    {"sign": "射手座", "symbol": "♐", "element": "火", "ruler": "木星",
     "start": (11, 23), "end": (12, 21)},
]

def get_zodiac(month, day):
    for z in ZODIAC_SIGNS:
        sm, sd = z["start"]
        em, ed = z["end"]
        if sm > em:  # 山羊座：12月〜1月
            if (month == sm and day >= sd) or (month == em and day <= ed):
                return z
        else:
            if (month == sm and day >= sd) or (month == em and day <= ed) or (sm < month < em):
                return z
    return ZODIAC_SIGNS[0]

# ─── 動物占い（12動物キャラクター）──────────────────────────────
ANIMALS = [
    {"name": "狼", "emoji": "🐺", "group": "地球グループ",
     "traits": "独立心が強く、マイペースな実力派。一人の時間を大切にする"},
    {"name": "こじか", "emoji": "🦌", "group": "月グループ",
     "traits": "純粋で人懐っこい。繊細な感性を持ち、警戒心も強い"},
    {"name": "猿", "emoji": "🐵", "group": "太陽グループ",
     "traits": "器用で社交的。頭の回転が速く、場を明るくする力がある"},
    {"name": "チータ", "emoji": "🐆", "group": "地球グループ",
     "traits": "スタートダッシュが得意で情熱的。直感力に優れている"},
    {"name": "黒ひょう", "emoji": "🐈\u200d⬛", "group": "月グループ",
     "traits": "感性豊かで美意識が高い。プライドが高く、独自の世界観がある"},
    {"name": "ライオン", "emoji": "🦁", "group": "太陽グループ",
     "traits": "堂々としたリーダー気質。面倒見がよく、人望がある"},
    {"name": "虎", "emoji": "🐅", "group": "地球グループ",
     "traits": "正義感が強い親分肌。面倒見がよく、人に尽くすタイプ"},
    {"name": "たぬき", "emoji": "🦝", "group": "月グループ",
     "traits": "社交上手で、人から好かれる調整役。愛嬌がある"},
    {"name": "コアラ", "emoji": "🐨", "group": "太陽グループ",
     "traits": "のんびりしているが実は戦略家。サービス精神旺盛"},
    {"name": "ゾウ", "emoji": "🐘", "group": "地球グループ",
     "traits": "努力家で粘り強い。信頼される存在で、コツコツ型"},
    {"name": "ひつじ", "emoji": "🐑", "group": "月グループ",
     "traits": "仲間思いで寂しがり屋。情に厚く、人とのつながりを大切にする"},
    {"name": "ペガサス", "emoji": "🦄", "group": "太陽グループ",
     "traits": "自由奔放な天才肌。束縛を嫌い、気分で動くタイプ"},
]

# 動物占い用：基準日からの日数で12キャラに振り分け
# 基準日: 1900年1月1日 = 狼(index 0)
ANIMAL_EPOCH = date(1900, 1, 1)

def get_animal(year, month, day):
    try:
        d = date(year, month, day)
        days = (d - ANIMAL_EPOCH).days
        idx = days % 12
        return ANIMALS[idx]
    except ValueError:
        return ANIMALS[0]

# ─── 算命術（天干・地支・五行）──────────────────────────────────
HEAVENLY_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
EARTHLY_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

STEM_TO_ELEMENT = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}

ELEMENT_INFO = {
    "木": {"name": "木（もく）", "emoji": "🌳", "nature": "成長・発展・創造",
           "color": "#2E7D32", "advice": "自然の中で過ごす時間を増やすと運気UP"},
    "火": {"name": "火（か）", "emoji": "🔥", "nature": "情熱・表現・直感",
           "color": "#D32F2F", "advice": "朝日を浴びる習慣で、内なる炎が安定します"},
    "土": {"name": "土（ど）", "emoji": "🏔️", "nature": "安定・信頼・包容力",
           "color": "#795548", "advice": "大地に足をつけるグラウンディングがおすすめ"},
    "金": {"name": "金（きん）", "emoji": "✨", "nature": "決断・実行・浄化",
           "color": "#FFC107", "advice": "ゴールドやシルバーのアクセサリーが開運のカギ"},
    "水": {"name": "水（すい）", "emoji": "💧", "nature": "知恵・柔軟・浄化",
           "color": "#1565C0", "advice": "水辺に出かけたり、水をたくさん飲むことで運気が流れます"},
}

BRANCH_TO_ANIMAL = {
    "子": "ねずみ", "丑": "うし", "寅": "とら", "卯": "うさぎ",
    "辰": "たつ", "巳": "へび", "午": "うま", "未": "ひつじ",
    "申": "さる", "酉": "とり", "戌": "いぬ", "亥": "いのしし",
}

def get_gogyo(year):
    stem_idx = (year - 4) % 10
    branch_idx = (year - 4) % 12
    stem = HEAVENLY_STEMS[stem_idx]
    branch = EARTHLY_BRANCHES[branch_idx]
    element = STEM_TO_ELEMENT[stem]
    return {
        "stem": stem,
        "branch": branch,
        "eto_animal": BRANCH_TO_ANIMAL[branch],
        "element": element,
        "element_info": ELEMENT_INFO[element],
    }

# ─── 生年月日パーサー ─────────────────────────────────────────
def parse_birthday(text):
    text = text.strip().replace(" ", "").replace("　", "")
    # 1990年3月15日
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日?", text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    # 1990/3/15 or 1990-3-15
    m = re.match(r"(\d{4})[/\-\.] ?(\d{1,2})[/\-\.] ?(\d{1,2})", text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    # 19900315
    m = re.match(r"(\d{4})(\d{2})(\d{2})$", text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None

def validate_birthday(year, month, day):
    try:
        d = date(year, month, day)
        return 1920 <= year <= 2015
    except ValueError:
        return False

# ─── セッション管理 ───────────────────────────────────────────
sessions = {}

def get_session(user_id):
    if user_id not in sessions:
        sessions[user_id] = {
            "step": "idle",
            "name": "",
            "birthday": "",
            "birth_year": 0,
            "birth_month": 0,
            "birth_day": 0,
            "gender": "",
            "concern_category": "",
            "concern_text": "",
            "zodiac": {},
            "animal": {},
            "gogyo": {},
            "booking_date": "",
        }
    return sessions[user_id]

def reset_session(user_id):
    if user_id in sessions:
        del sessions[user_id]

# ─── LINE API ─────────────────────────────────────────────────
def reply(reply_token, messages):
    if not isinstance(messages, list):
        messages = [messages]
    body = json.dumps({"replyToken": reply_token, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        LINE_REPLY_API,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        },
        method="POST",
    )
    try:
        res = urllib.request.urlopen(req)
        print(f"[REPLY OK] status={res.status}", flush=True)
    except Exception as e:
        print(f"[REPLY ERROR] {e}", flush=True)

def push_message(to_user_id, messages):
    if not to_user_id:
        return
    if not isinstance(messages, list):
        messages = [messages]
    body = json.dumps({"to": to_user_id, "messages": messages}).encode("utf-8")
    req = urllib.request.Request(
        LINE_PUSH_API,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}",
        },
        method="POST",
    )
    try:
        res = urllib.request.urlopen(req)
        print(f"[PUSH OK] status={res.status}", flush=True)
    except Exception as e:
        print(f"[PUSH ERROR] {e}", flush=True)

# ─── Quick Reply ビルダー ─────────────────────────────────────
def make_gender_quick_reply():
    return {
        "type": "text",
        "text": "🌸 性別を教えてください",
        "quickReply": {
            "items": [
                {"type": "action", "action": {"type": "postback", "label": "♀ 女性",
                 "data": "gender=女性", "displayText": "女性"}},
                {"type": "action", "action": {"type": "postback", "label": "♂ 男性",
                 "data": "gender=男性", "displayText": "男性"}},
                {"type": "action", "action": {"type": "postback", "label": "✨ その他",
                 "data": "gender=その他", "displayText": "その他"}},
            ],
        },
    }

def make_category_quick_reply():
    categories = [
        ("💕", "恋愛"), ("💼", "仕事"), ("👥", "人間関係"),
        ("💰", "金運"), ("🏥", "健康"), ("🌈", "全体運"),
    ]
    return {
        "type": "text",
        "text": "🔮 今、一番気になるお悩みのジャンルは？",
        "quickReply": {
            "items": [
                {"type": "action", "action": {"type": "postback",
                 "label": f"{emoji} {name}", "data": f"category={name}",
                 "displayText": name}}
                for emoji, name in categories
            ],
        },
    }

# ─── 予約システム ─────────────────────────────────────────────
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]

TIME_SLOTS = [
    "10:00〜11:00",
    "11:00〜12:00",
    "12:00〜13:00",
    "13:00〜14:00",
    "14:00〜15:00",
    "15:00〜16:00",
    "19:00〜20:00",
    "20:00〜21:00",
]

def get_next_7days():
    today = datetime.utcnow() + timedelta(hours=9)  # JST
    days = []
    for i in range(1, 8):
        d = today + timedelta(days=i)
        wd = WEEKDAY_JP[d.weekday()]
        label = f"{d.month}/{d.day}（{wd}）"
        value = d.strftime("%Y-%m-%d")
        days.append({"label": label, "value": value})
    return days

def make_date_picker_msg():
    days = get_next_7days()
    items = [
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": d["label"],
                "data": f"booking_date={d['value']}",
                "displayText": d["label"],
            },
        }
        for d in days
    ]
    return {
        "type": "text",
        "text": "🌙 ご都合の良い日をお選びください",
        "quickReply": {"items": items},
    }

def make_time_picker_msg():
    items = [
        {
            "type": "action",
            "action": {
                "type": "postback",
                "label": slot,
                "data": f"booking_time={slot}",
                "displayText": slot,
            },
        }
        for slot in TIME_SLOTS
    ]
    return {
        "type": "text",
        "text": "⏰ ご希望の時間帯をお選びください",
        "quickReply": {"items": items},
    }

def make_booking_confirm_flex(date_str, time_slot, user_name=""):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    wd = WEEKDAY_JP[d.weekday()]
    display_date = f"{d.year}年{d.month}月{d.day}日（{wd}）"
    return {
        "type": "flex",
        "altText": f"個別鑑定のご予約：{display_date} {time_slot}",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "✅ ご予約を受け付けました",
                     "weight": "bold", "size": "lg", "align": "center", "color": "#ffffff"},
                ],
                "backgroundColor": "#5a2da0",
                "paddingAll": "16px",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "🔮 個別スピリチュアル鑑定",
                     "weight": "bold", "size": "lg", "align": "center", "margin": "md"},
                    {"type": "separator", "margin": "lg"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "👤 お名前", "size": "sm",
                                     "color": "#888888", "flex": 2},
                                    {"type": "text", "text": user_name or "（未入力）",
                                     "size": "sm", "weight": "bold", "color": "#333333",
                                     "flex": 5, "wrap": True},
                                ],
                                "margin": "lg",
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "📅 日時", "size": "sm",
                                     "color": "#888888", "flex": 2},
                                    {"type": "text", "text": display_date, "size": "sm",
                                     "weight": "bold", "color": "#333333", "flex": 5,
                                     "wrap": True},
                                ],
                                "margin": "md",
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "⏰ 時間", "size": "sm",
                                     "color": "#888888", "flex": 2},
                                    {"type": "text", "text": time_slot, "size": "sm",
                                     "weight": "bold", "color": "#333333", "flex": 5},
                                ],
                                "margin": "md",
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {"type": "text", "text": "💻 形式", "size": "sm",
                                     "color": "#888888", "flex": 2},
                                    {"type": "text", "text": "オンライン（Zoom）", "size": "sm",
                                     "weight": "bold", "color": "#333333", "flex": 5},
                                ],
                                "margin": "md",
                            },
                        ],
                        "backgroundColor": "#f2ecff",
                        "cornerRadius": "10px",
                        "paddingAll": "16px",
                        "margin": "lg",
                    },
                    {"type": "text",
                     "text": "確認のご連絡をお送りしますので\n少々お待ちください🙏✨",
                     "size": "sm", "color": "#555555", "wrap": True,
                     "align": "center", "margin": "lg"},
                ],
                "paddingAll": "20px",
            },
        },
    }

# ─── Claude API 鑑定生成 ─────────────────────────────────────
SYSTEM_PROMPT = """あなたは温かく寄り添うスピリチュアルカウンセラーです。
相談者の占術データと悩みをもとに、愛と光に満ちた鑑定結果をお届けします。

【ルール】
- 相談者の名前を呼びかけながら、親しみを込めて語りかけてください
- 否定的な表現は避け、課題も「成長のチャンス」として前向きに伝えてください
- 具体的で実践しやすいアドバイスを含めてください
- スピリチュアルな表現（宇宙、エネルギー、波動など）を適度に使ってください
- 各セクションは簡潔に（2〜3文程度）
- 総合メッセージは相談者の具体的な悩みに寄り添ってください"""

def build_divination_prompt(session):
    zodiac = session.get("zodiac", {})
    animal = session.get("animal", {})
    gogyo = session.get("gogyo", {})
    ei = gogyo.get("element_info", {})

    return f"""以下の情報に基づいて、総合鑑定結果を作成してください。

【依頼者情報】
お名前: {session['name']}
生年月日: {session['birthday']}
性別: {session['gender']}

【占術データ】
■ 西洋占星術: {zodiac.get('sign', '')} {zodiac.get('symbol', '')}
  エレメント: {zodiac.get('element', '')} / 守護星: {zodiac.get('ruler', '')}

■ 動物占い: {animal.get('emoji', '')} {animal.get('name', '')}（{animal.get('group', '')}）
  特徴: {animal.get('traits', '')}

■ 算命術 五行: {ei.get('name', '')} {ei.get('emoji', '')}
  天干: {gogyo.get('stem', '')} / 地支: {gogyo.get('branch', '')}（{gogyo.get('eto_animal', '')}年）
  性質: {ei.get('nature', '')}

【お悩みカテゴリ】{session['concern_category']}
【具体的なお悩み】{session['concern_text']}

以下の5セクションで回答してください。セクション名は【】で囲んでください:

【西洋占星術メッセージ】
（星座の特徴と悩みに関連する2〜3文）

【動物占いメッセージ】
（動物キャラの特徴と悩みに関連する2〜3文）

【算命術メッセージ】
（五行の特徴と悩みに関連する2〜3文）

【総合メッセージ】
（3つの占術を統合した、悩みへの具体的アドバイス。4〜5文）

【開運アドバイス】
（具体的な開運行動を3つ、箇条書き。各1行で）"""

def parse_reading_sections(text):
    sections = {}
    patterns = [
        ("western", r"【西洋占星術メッセージ】\s*(.*?)(?=【|$)"),
        ("animal", r"【動物占いメッセージ】\s*(.*?)(?=【|$)"),
        ("gogyo", r"【算命術メッセージ】\s*(.*?)(?=【|$)"),
        ("comprehensive", r"【総合メッセージ】\s*(.*?)(?=【|$)"),
        ("advice", r"【開運アドバイス】\s*(.*?)(?=【|$)"),
    ]
    for key, pattern in patterns:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            sections[key] = m.group(1).strip()
        else:
            sections[key] = ""
    return sections

def generate_and_send_reading(user_id, session_data):
    """バックグラウンドスレッドで実行: Claude APIで鑑定生成→Push APIで送信"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        prompt = build_divination_prompt(session_data)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        reading_text = response.content[0].text
        parsed = parse_reading_sections(reading_text)

        flex_msg = make_divination_result_flex(session_data, parsed)
        push_message(user_id, flex_msg)
        print(f"[DIVINATION OK] user={user_id[:8]}", flush=True)

    except Exception as e:
        print(f"[DIVINATION ERROR] {e}", flush=True)
        push_message(user_id, {
            "type": "text",
            "text": "🙏 申し訳ございません。\n鑑定に少しお時間がかかっています。\n\nもう少々お待ちいただくか、\n再度「占い」とお送りください🔮",
        })

# ─── 鑑定結果 Flex Message ────────────────────────────────────
def _make_section_box(title, subtitle, body_text, accent_color):
    return {
        "type": "box",
        "layout": "vertical",
        "contents": [
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": title, "weight": "bold",
                     "size": "sm", "color": accent_color, "flex": 6},
                    {"type": "text", "text": subtitle, "size": "sm",
                     "color": "#333333", "align": "end", "weight": "bold", "flex": 4},
                ],
                "alignItems": "center",
            },
            {"type": "text", "text": body_text or "...", "size": "xs",
             "color": "#555555", "wrap": True, "margin": "sm"},
        ],
        "margin": "lg",
    }

def make_divination_result_flex(session, parsed):
    zodiac = session.get("zodiac", {})
    animal = session.get("animal", {})
    gogyo = session.get("gogyo", {})
    ei = gogyo.get("element_info", {})

    return {
        "type": "flex",
        "altText": f"🔮 {session['name']}さんの総合鑑定結果",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "🔮✨ 総合鑑定結果 ✨🔮",
                     "weight": "bold", "size": "lg", "align": "center",
                     "color": "#e8c44a"},
                    {"type": "text",
                     "text": f"{session['name']} さん",
                     "size": "md", "align": "center", "color": "#ffffff",
                     "margin": "sm"},
                    {"type": "text",
                     "text": f"{session['birthday']} | {session['gender']}",
                     "size": "xxs", "align": "center", "color": "#b3a0d0",
                     "margin": "xs"},
                ],
                "backgroundColor": "#1a0b30",
                "paddingAll": "20px",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    # ── 西洋占星術 ──
                    _make_section_box(
                        f"🌟 西洋占星術",
                        f"{zodiac.get('symbol', '')} {zodiac.get('sign', '')}",
                        parsed.get("western", ""),
                        "#5a2da0",
                    ),
                    {"type": "separator", "margin": "lg"},
                    # ── 動物占い ──
                    _make_section_box(
                        f"🐾 動物占い",
                        f"{animal.get('emoji', '')} {animal.get('name', '')}",
                        parsed.get("animal", ""),
                        "#2E7D32",
                    ),
                    {"type": "separator", "margin": "lg"},
                    # ── 算命術 五行 ──
                    _make_section_box(
                        f"☯️ 算命術（五行）",
                        f"{ei.get('emoji', '')} {ei.get('name', '')}",
                        parsed.get("gogyo", ""),
                        ei.get("color", "#795548"),
                    ),
                    {"type": "separator", "margin": "lg"},
                    # ── 総合メッセージ ──
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {"type": "text", "text": "💫 総合メッセージ",
                             "weight": "bold", "size": "sm", "color": "#c9a227"},
                            {"type": "text",
                             "text": parsed.get("comprehensive", "") or "...",
                             "size": "xs", "color": "#333333", "wrap": True,
                             "margin": "sm"},
                        ],
                        "margin": "lg",
                        "backgroundColor": "#f2ecff",
                        "cornerRadius": "10px",
                        "paddingAll": "14px",
                    },
                    {"type": "separator", "margin": "lg"},
                    # ── 開運アドバイス ──
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {"type": "text", "text": "🔮 開運アドバイス",
                             "weight": "bold", "size": "sm", "color": "#c9a227"},
                            {"type": "text",
                             "text": parsed.get("advice", "") or "...",
                             "size": "xs", "color": "#555555", "wrap": True,
                             "margin": "sm"},
                        ],
                        "margin": "lg",
                        "backgroundColor": "#fef9f0",
                        "cornerRadius": "10px",
                        "paddingAll": "14px",
                    },
                ],
                "paddingAll": "20px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "🌙 もっと詳しく聞く（個別鑑定予約）",
                            "data": "action=start_booking",
                            "displayText": "もっと詳しく聞きたいです",
                        },
                        "style": "primary",
                        "color": "#5a2da0",
                        "height": "sm",
                    },
                    {"type": "text",
                     "text": "※ より深い個別鑑定のご予約ができます",
                     "size": "xxs", "color": "#aaaaaa", "align": "center",
                     "margin": "sm"},
                ],
                "paddingAll": "16px",
            },
        },
    }

# ─── イベントハンドラー ───────────────────────────────────────
def handle_event(event):
    user_id = event.get("source", {}).get("userId", "")
    reply_token = event.get("replyToken", "")
    event_type = event.get("type", "")

    # ─── フォローイベント ───
    if event_type == "follow":
        reply(reply_token, {
            "type": "text",
            "text": "🔮 ようこそ✨\nスピリチュアル総合鑑定へ\n\n"
                    "算命術・ホロスコープ・動物占いの\n"
                    "3つの占術を組み合わせて\n"
                    "あなただけの鑑定をお届けします🌙\n\n"
                    "「占い」と送ると鑑定スタート！",
        })
        return

    # ─── テキストメッセージ ───
    if event_type == "message" and event.get("message", {}).get("type") == "text":
        text = event["message"]["text"].strip()
        session = get_session(user_id)
        step = session["step"]

        # トリガーワード → 鑑定開始
        if text in ["占い", "鑑定", "スタート", "最初から", "もう一度"]:
            reset_session(user_id)
            session = get_session(user_id)
            session["step"] = "ask_name"
            reply(reply_token, {
                "type": "text",
                "text": "🔮 スピリチュアル総合鑑定を始めます✨\n\n"
                        "算命術・ホロスコープ・動物占いの\n"
                        "3つの占術を組み合わせて\n"
                        "あなただけの鑑定結果をお届けします🌙\n\n"
                        "まず、お名前（ニックネームでもOK）を\n"
                        "教えてください😊",
            })
            return

        # 予約トリガー
        if text in ["予約", "個別鑑定", "相談"]:
            session["step"] = "booking_date"
            reply(reply_token, [
                {"type": "text", "text": "🌙 個別鑑定のご予約を承ります✨\n\nご都合の良い日をお選びください"},
                make_date_picker_msg(),
            ])
            return

        # ─── ステップ別処理 ───
        if step == "ask_name":
            session["name"] = text
            session["step"] = "ask_birthday"
            reply(reply_token, {
                "type": "text",
                "text": f"{text}さん✨\n素敵なお名前ですね🌸\n\n"
                        "次に、生年月日を教えてください🎂\n\n"
                        "例: 1990年3月15日\n"
                        "（1990/3/15 でもOKです）",
            })

        elif step == "ask_birthday":
            parsed = parse_birthday(text)
            if parsed is None or not validate_birthday(*parsed):
                reply(reply_token, {
                    "type": "text",
                    "text": "🙏 ごめんなさい、読み取れませんでした。\n\n"
                            "「1990年3月15日」のように\n"
                            "入力してくださいね✨",
                })
                return
            year, month, day = parsed
            session["birthday"] = f"{year}年{month}月{day}日"
            session["birth_year"] = year
            session["birth_month"] = month
            session["birth_day"] = day
            session["zodiac"] = get_zodiac(month, day)
            session["animal"] = get_animal(year, month, day)
            session["gogyo"] = get_gogyo(year)
            session["step"] = "ask_gender"
            reply(reply_token, make_gender_quick_reply())

        elif step == "ask_concern":
            session["concern_text"] = text
            session["step"] = "generating"

            # 即時返信
            reply(reply_token, {
                "type": "text",
                "text": "🔮 鑑定中です✨\n\n"
                        "あなたの星の配置と\n"
                        "エネルギーの流れを読み解いています...\n\n"
                        "🌙 しばらくお待ちください 🌙",
            })

            # バックグラウンドでClaude API呼び出し
            session_copy = dict(session)
            thread = threading.Thread(
                target=generate_and_send_reading,
                args=(user_id, session_copy),
                daemon=True,
            )
            thread.start()

        elif step == "generating":
            reply(reply_token, {
                "type": "text",
                "text": "🔮 現在鑑定中です✨\nもう少々お待ちくださいね🌙",
            })

        else:
            # idle / 未知のステップ
            reply(reply_token, {
                "type": "text",
                "text": "🔮 スピリチュアル総合鑑定へようこそ✨\n\n"
                        "「占い」と送ると鑑定を開始します🌙\n"
                        "「予約」で個別鑑定のご予約もできます✨",
            })

    # ─── ポストバック ───
    elif event_type == "postback":
        session = get_session(user_id)
        data = parse_qs(event["postback"]["data"])

        # 性別選択
        if "gender" in data:
            session["gender"] = data["gender"][0]
            session["step"] = "ask_category"
            reply(reply_token, make_category_quick_reply())

        # 悩みカテゴリ選択
        elif "category" in data:
            session["concern_category"] = data["category"][0]
            session["step"] = "ask_concern"
            reply(reply_token, {
                "type": "text",
                "text": f"🌙 {data['category'][0]}のお悩みですね\n\n"
                        "具体的にどんなことで\n"
                        "悩んでいますか？\n\n"
                        "自由にお話しください✨\n"
                        "（一言でも長文でもOKです）",
            })

        # 予約開始
        elif "action" in data and data["action"][0] == "start_booking":
            session["step"] = "booking_date"
            reply(reply_token, [
                {"type": "text", "text": "🌙 個別鑑定のご予約\nありがとうございます✨\n\nご都合の良い日をお選びください"},
                make_date_picker_msg(),
            ])

        # 日付選択
        elif "booking_date" in data:
            session["booking_date"] = data["booking_date"][0]
            session["step"] = "booking_time"
            reply(reply_token, make_time_picker_msg())

        # 時間帯選択 → 予約確定
        elif "booking_time" in data:
            selected_time = data["booking_time"][0]
            booking_date = session.get("booking_date", "")
            user_name = session.get("name", "")

            if not booking_date:
                reply(reply_token, {"type": "text",
                      "text": "🙏 もう一度「予約」と送ってください"})
                reset_session(user_id)
                return

            # ユーザーに確認
            reply(reply_token, make_booking_confirm_flex(
                booking_date, selected_time, user_name))

            # オーナーに通知
            d = datetime.strptime(booking_date, "%Y-%m-%d")
            wd = WEEKDAY_JP[d.weekday()]
            display_date = f"{d.year}年{d.month}月{d.day}日（{wd}）"
            concern = session.get("concern_category", "")
            push_message(OWNER_USER_ID, {
                "type": "text",
                "text": f"📩 新しい個別鑑定の予約が入りました！\n\n"
                        f"👤 お名前: {user_name or '未入力'}\n"
                        f"🔮 お悩み: {concern or '未入力'}\n"
                        f"📅 日時: {display_date}\n"
                        f"⏰ 時間: {selected_time}\n\n"
                        f"確認連絡をお願いします🙏",
            })

            print(f"[BOOKING] user={user_id[:8]} name={user_name} "
                  f"date={booking_date} time={selected_time}", flush=True)
            reset_session(user_id)

# ─── HTTP サーバー ────────────────────────────────────────────
def verify_signature(body, signature):
    hash_ = hmac.new(
        CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256
    ).digest()
    return base64.b64encode(hash_).decode("utf-8") == signature

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Spiritual Bot running OK")

    def do_POST(self):
        print(f"[POST] path={self.path}", flush=True)
        if self.path not in ("/webhook", "/callback"):
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        signature = self.headers.get("X-Line-Signature", "")
        print(f"[SIG] len={len(body)} sig={signature[:20]}...", flush=True)

        if not verify_signature(body, signature):
            print("[403] signature mismatch", flush=True)
            self.send_response(403)
            self.end_headers()
            return

        try:
            data = json.loads(body.decode("utf-8"))
            events = data.get("events", [])
            print(f"[EVENTS] count={len(events)}", flush=True)
            for event in events:
                eid = event.get("source", {}).get("userId", "?")[:8]
                print(f"[EVENT] type={event.get('type')} userId={eid}",
                      flush=True)
                handle_event(event)
        except Exception as e:
            print(f"[ERROR] {e}", flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"🔮 Spiritual Bot running on port {port}")
    server.serve_forever()
