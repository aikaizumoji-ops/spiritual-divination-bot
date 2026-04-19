import os
import hashlib
import hmac
import base64
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
import urllib.request
from datetime import datetime, timedelta, date
import random

# ─── 環境変数 ──────────────────────────────────────────────────
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
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
        if sm > em:
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
    text = text.strip().replace(" ", "").replace("\u3000", "")
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日?", text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.match(r"(\d{4})[/\-\.] ?(\d{1,2})[/\-\.] ?(\d{1,2})", text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.match(r"(\d{4})(\d{2})(\d{2})$", text)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None

def validate_birthday(year, month, day):
    try:
        date(year, month, day)
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
            "birth_year": 0, "birth_month": 0, "birth_day": 0,
            "gender": "",
            "concern_category": "",
            "concern_text": "",
            "zodiac": {}, "animal": {}, "gogyo": {},
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
        LINE_REPLY_API, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
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
        LINE_PUSH_API, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
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
        ("🧲", "集客"), ("💎", "商品設計"), ("🤝", "セールス"),
        ("🧠", "マインド"), ("⚙️", "仕組み化"), ("🌈", "経営全体"),
    ]
    return {
        "type": "text",
        "text": "💎 今、一番向き合いたい経営テーマは？",
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
    "10:00〜11:00", "11:00〜12:00", "12:00〜13:00", "13:00〜14:00",
    "14:00〜15:00", "15:00〜16:00", "19:00〜20:00", "20:00〜21:00",
]

def get_next_7days():
    today = datetime.utcnow() + timedelta(hours=9)
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
        {"type": "action", "action": {"type": "postback", "label": d["label"],
         "data": f"booking_date={d['value']}", "displayText": d["label"]}}
        for d in days
    ]
    return {"type": "text", "text": "🌙 ご都合の良い日をお選びください",
            "quickReply": {"items": items}}

def make_time_picker_msg():
    items = [
        {"type": "action", "action": {"type": "postback", "label": slot,
         "data": f"booking_time={slot}", "displayText": slot}}
        for slot in TIME_SLOTS
    ]
    return {"type": "text", "text": "⏰ ご希望の時間帯をお選びください",
            "quickReply": {"items": items}}

def make_booking_confirm_flex(date_str, time_slot, user_name=""):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    wd = WEEKDAY_JP[d.weekday()]
    display_date = f"{d.year}年{d.month}月{d.day}日（{wd}）"
    return {
        "type": "flex", "altText": f"個別経営コンサルのご予約：{display_date} {time_slot}",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "vertical",
                "contents": [{"type": "text", "text": "✅ ご予約を受け付けました",
                    "weight": "bold", "size": "lg", "align": "center", "color": "#ffffff"}],
                "backgroundColor": "#5a2da0", "paddingAll": "16px"},
            "body": {"type": "box", "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "💎 個別経営コンサルティング",
                     "weight": "bold", "size": "lg", "align": "center", "margin": "md"},
                    {"type": "separator", "margin": "lg"},
                    {"type": "box", "layout": "vertical",
                     "contents": [
                         {"type": "box", "layout": "horizontal", "margin": "lg",
                          "contents": [
                              {"type": "text", "text": "👤 お名前", "size": "sm", "color": "#888888", "flex": 2},
                              {"type": "text", "text": user_name or "（未入力）", "size": "sm", "weight": "bold", "color": "#333333", "flex": 5, "wrap": True}]},
                         {"type": "box", "layout": "horizontal", "margin": "md",
                          "contents": [
                              {"type": "text", "text": "📅 日時", "size": "sm", "color": "#888888", "flex": 2},
                              {"type": "text", "text": display_date, "size": "sm", "weight": "bold", "color": "#333333", "flex": 5, "wrap": True}]},
                         {"type": "box", "layout": "horizontal", "margin": "md",
                          "contents": [
                              {"type": "text", "text": "⏰ 時間", "size": "sm", "color": "#888888", "flex": 2},
                              {"type": "text", "text": time_slot, "size": "sm", "weight": "bold", "color": "#333333", "flex": 5}]},
                         {"type": "box", "layout": "horizontal", "margin": "md",
                          "contents": [
                              {"type": "text", "text": "💻 形式", "size": "sm", "color": "#888888", "flex": 2},
                              {"type": "text", "text": "オンライン（Zoom）", "size": "sm", "weight": "bold", "color": "#333333", "flex": 5}]},
                     ],
                     "backgroundColor": "#f2ecff", "cornerRadius": "10px", "paddingAll": "16px", "margin": "lg"},
                    {"type": "text", "text": "確認のご連絡をお送りしますので\n少々お待ちください🙏✨",
                     "size": "sm", "color": "#555555", "wrap": True, "align": "center", "margin": "lg"},
                ], "paddingAll": "20px"},
        },
    }

# ─── テンプレートベース鑑定生成（即時・API不要）──────────────────

ZODIAC_MESSAGES = {
    "集客": {
        "火": [
            "{name}さんの{sign}は{ruler}の後押しで、発信力と熱量が際立つ経営タイプ。SNSやライブ配信など「熱」が伝わる場が集客の主戦場。あなた自身のストーリーを堂々と語ることが、そのまま見込み客の心を動かします。",
            "{name}さんは火のエレメント。情熱×スピードの即動型リーダー。集客では「完璧に整えてから」より「走りながら整える」方が圧倒的に数字が伸びます。まず1本発信しましょう。",
        ],
        "地": [
            "{name}さんの{sign}は{ruler}守護の堅実タイプ。集客は「積み上げ型」が最強。ブログ・LP・メルマガなど資産化されるコンテンツが中心戦略。派手さより継続が信頼に変わります。",
            "{name}さんは地のエレメント。じっくりファン化していく力が強み。短期の爆発より、半年〜1年で安定した導線を作るアプローチが成果に直結します。",
        ],
        "風": [
            "{name}さんの{sign}は{ruler}の影響で発想力と言語化力が光る経営タイプ。X・Threads・Podcastなど「言葉」で拡散するチャネルとの相性が抜群。切り口と編集で差をつけましょう。",
            "{name}さんは風のエレメント。トレンドを掴む感度と軽やかさが武器。コラボ・対談・引用など「人の輪を広げる集客」で爆発的に露出が伸びる時期です。",
        ],
        "水": [
            "{name}さんの{sign}は{ruler}の深い洞察で、顧客の無言のニーズを感じ取る力が抜群。集客では「刺さる言葉」を書ける人。ペルソナ1人に徹底的に寄り添うメッセージが選ばれる鍵です。",
            "{name}さんは水のエレメント。共感と癒しのブランディングが最強。動画・音声・手紙調のメルマガなど、温度を感じさせる媒体で深いファンが集まります。",
        ],
    },
    "商品設計": {
        "火": ["{name}さんの{sign}は{ruler}の力で、即断即決のパワー型。商品は「本気で人生を変えたい人向けの高単価・短期集中」設計が合います。値付けに迷わず、堂々と価格を打ち出して。"],
        "地": ["{name}さんの{sign}は{ruler}守護の実務派。6ヶ月〜1年の伴走型プログラム、段階的な階段設計（フロント→バック）で安心感のある商品構造を作れます。分割払い設計もおすすめ。"],
        "風": ["{name}さんの{sign}は{ruler}の知的なエネルギーで、独自コンセプトを言語化する力が武器。USPと商品名、セールスコピーにこだわるほど単価を上げても売れます。"],
        "水": ["{name}さんの{sign}は{ruler}の深い感受性で、顧客の変容に寄り添う商品が最強。1対1のセッション型、グループ型でも少人数高単価の設計が最も成果に繋がります。"],
    },
    "セールス": {
        "火": ["{name}さんの{sign}は熱量で人を動かすセールスタイプ。個別相談・ウェビナーなど「対話の熱」で成約する場面で本領発揮。クロージングで遠慮しないことが大切です。"],
        "地": ["{name}さんの{sign}は誠実さと実績提示で信頼を勝ち取るタイプ。Before/Afterの事例、数字、お客様の声を丁寧に見せることで、迷っている人の背中を押せます。"],
        "風": ["{name}さんの{sign}は論理的な説明力でセールスを成功させるタイプ。価値提案と導入後の未来を言語化できれば、高単価でも納得感を持って契約に至ります。"],
        "水": ["{name}さんの{sign}は共感型セールス。相手の本音を引き出すヒアリングが最大の武器。「売る」のではなく「未来を一緒に見る」姿勢が、スピ業界特有の罪悪感を溶かします。"],
    },
    "マインド": {
        "火": ["{name}さんの{sign}は本来パワフルな行動派。でも「稼ぐのは汚い」というブロックが燃料を止めることがあります。お金=エネルギーの循環と捉え直すと、売上が一気に動きます。"],
        "地": ["{name}さんの{sign}は慎重さゆえに「まだ準備が足りない」と足踏みしがち。完璧主義のブロックを外し「70%でリリース」を合言葉に。行動が自信を育てます。"],
        "風": ["{name}さんの{sign}は考えすぎて動けなくなる傾向があります。「感性を信じる＝論理の先回り」と理解すると、直感的な決断に罪悪感がなくなり、事業スピードが上がります。"],
        "水": ["{name}さんの{sign}は人の感情を受けすぎて疲弊しやすいタイプ。値上げや断る罪悪感のブロックを解除することが最優先。自分を満たすことが最大のビジネス戦略です。"],
    },
    "仕組み化": {
        "火": ["{name}さんの{sign}は瞬発力が武器ですが、属人労働に陥りがち。自動ウェビナー・LINE公式のステップ配信で「自分が寝ていても売れる導線」を作ることが次のステージへの鍵。"],
        "地": ["{name}さんの{sign}は元々仕組みを作る才能あり。SOP化・テンプレート化・外注化で、自分の時間を30%削減するだけで売上が1.5倍になるケースが多い配置です。"],
        "風": ["{name}さんの{sign}はツール選定と情報整理が得意。Notion・ChatGPT・自動化ツールを組み合わせれば、バックオフィスの生産性が倍増するタイミングに来ています。"],
        "水": ["{name}さんの{sign}は感性型ゆえに「仕組み化＝冷たい」と感じがちですが、仕組み化こそクライアントに深く向き合う時間を生みます。まずLINE導線からで十分です。"],
    },
    "経営全体": {
        "火": ["{name}さんの{sign}は今、拡大フェーズのエネルギー最高潮。{ruler}の後押しで大胆な挑戦が吉。ただし属人労働から仕組みへの転換を同時進行で。単月最高売上を更新する配置。"],
        "地": ["{name}さんの{sign}は今、基盤が強固に固まる時期。{ruler}のサポートで安定収益の仕組みが整います。派手な成長ではなく、離脱率ゼロの強固な顧客基盤を作るフェーズ。"],
        "風": ["{name}さんの{sign}は今、新しいビジネスモデルが降りてくる時期。{ruler}の影響で出会い・情報・コラボからピボットのヒントが届きます。学びへの投資が加速器に。"],
        "水": ["{name}さんの{sign}は今、深い変容のタイミング。{ruler}があなたの感性を磨き、本当に届けたい相手が明確になります。ペルソナを1人に絞る勇気が飛躍のカギ。"],
    },
}

# 旧カテゴリ辞書は削除済み

ANIMAL_MESSAGES = {
    "集客": "{name}さんの経営キャラ「{animal_name}」は{traits_short}タイプ。集客では{animal_shukaku}。{group}のエネルギーが発信スタイルを後押しします。",
    "商品設計": "{name}さんの経営キャラ「{animal_name}」は{traits_short}タイプ。商品設計では{animal_product}。{group}らしい商品構造がベストマッチです。",
    "セールス": "{name}さんの経営キャラ「{animal_name}」は{traits_short}タイプ。セールスでは{animal_sales}。{group}の持ち味がそのままクロージング力になります。",
    "マインド": "{name}さんの経営キャラ「{animal_name}」は{traits_short}タイプ。マインド面では{animal_mind}。{group}の傾向を理解すると、ブロックが解けます。",
    "仕組み化": "{name}さんの経営キャラ「{animal_name}」は{traits_short}タイプ。仕組み化では{animal_system}。{group}特有のボトルネックを先回りで潰すのがコツ。",
    "経営全体": "{name}さんの経営キャラ「{animal_name}」は{traits_short}タイプ。今の経営フェーズは{animal_overall}。{group}の強みを信じて進んでください。",
}

ANIMAL_DETAILS = {
    "狼":     {"traits_short": "独立心が強い単独プロフェッショナル型", "animal_shukaku": "少数精鋭のコアファン育成型が最適。深い世界観を発信する濃いコンテンツが刺さります", "animal_product": "1対1の個別セッション型・VIPコースなど、濃密な商品構造が最強", "animal_sales": "多くは語らず本質を突くスタイル。相手に深く考えさせる質問型クロージング", "animal_mind": "人に頼ることへのブロックを緩めると、外注・チーム化の壁が破れます", "animal_system": "一人で抱え込まず、最初の1人のアシスタント採用が転機に", "animal_overall": "質×深さで差別化する孤高の専門家ポジションが最適"},
    "こじか":  {"traits_short": "繊細で共感力の高い癒し系", "animal_shukaku": "ストーリー発信・手紙調メルマガなど、温度のある媒体でファン化", "animal_product": "少人数コミュニティ型・安心設計の6ヶ月プログラムが相性◎", "animal_sales": "押し売り感ゼロの寄り添いセールス。個別相談での丁寧なヒアリングで成約", "animal_mind": "「価値を受け取る罪悪感」を外すと、値上げの壁がスッと抜けます", "animal_system": "完璧主義を手放し、まずLINE公式の簡単な自動応答から始めましょう", "animal_overall": "安心と癒しのブランディングで選ばれ続ける顧客基盤ができる時期"},
    "猿":     {"traits_short": "器用で明るいマルチ発信型", "animal_shukaku": "複数SNS横断の多面的な発信が武器。短尺動画・リール系と抜群の相性", "animal_product": "単発商品×継続商品のハイブリッド設計で収益源を多角化", "animal_sales": "楽しく軽やかな会話でクロージング。体験会・茶話会形式が得意", "animal_mind": "飽き性を受け入れ、6ヶ月単位で事業をアップデートする前提設計が吉", "animal_system": "ツール好きを活かしNotion・AI自動化で一気に効率化できます", "animal_overall": "多面性を活かした複数収益源で年商アップが狙える配置"},
    "チータ":  {"traits_short": "瞬発力抜群のローンチ型", "animal_shukaku": "期間限定キャンペーン・ローンチ集客が大得意。短期爆発型", "animal_product": "3日〜1週間集中プログラムなど、スピード感ある商品が合います", "animal_sales": "勢いでクロージングする即決型。迷っている相手に決断を促すのが上手", "animal_mind": "「続けられない」ブロックを外し、助走より勢いで走り続ける戦略に", "animal_system": "スピードを維持するため、ルーティン業務を徹底的に外注・自動化", "animal_overall": "短期ローンチを年に数回打つ爆発型経営が最適なフェーズ"},
    "黒ひょう": {"traits_short": "美意識と感性で魅せるクリエイター型", "animal_shukaku": "ビジュアル美と世界観で差別化。Instagram・YouTubeが主戦場", "animal_product": "プレミアム×アート性の高い商品設計で高単価化が可能", "animal_sales": "感性で共鳴する相手を引き寄せるセールス。数より質で勝負", "animal_mind": "「ビジネス＝ダサい」の思い込みを手放すと、美しく稼げる道が見えます", "animal_system": "クリエイティブ時間を守るため、事務系は早期に手放しましょう", "animal_overall": "唯一無二のブランド確立で高単価帯へシフトする転機"},
    "ライオン": {"traits_short": "堂々としたリーダータイプ", "animal_shukaku": "権威性×実績で集める正攻法。出版・登壇・コラボが強力に効きます", "animal_product": "高額バックエンド・マスターマインド形式の主宰者ポジションが最適", "animal_sales": "説得力あるプレゼンで大口を決める力あり。ウェビナーで本領発揮", "animal_mind": "「完璧な先生であらねば」を緩めると、等身大で稼げる楽さが来ます", "animal_system": "チーム化を進め、あなたはフロントに専念する体制が売上倍増のカギ", "animal_overall": "法人化・スケール化を視野に入れるフェーズ。後進育成も運気UP"},
    "虎":     {"traits_short": "面倒見の良い親分型", "animal_shukaku": "コミュニティ型・仲間集めが強力。紹介による集客が最大チャネル", "animal_product": "伴走・コミット型の長期プログラム（6ヶ月〜1年）が相性抜群", "animal_sales": "相手の人生に本気でコミットする熱量型セールス。信頼で決まります", "animal_mind": "「全員を救わねば」を手放すと、理想クライアントだけに絞れます", "animal_system": "チームメンバーへの権限委譲が進むと、あなたの自由時間が増えます", "animal_overall": "コミュニティ経済圏を作る運気。会員制・サブスク化も視野に"},
    "たぬき":  {"traits_short": "場を和ませる調整上手", "animal_shukaku": "対談・コラボ発信が得意。横のつながりから紹介が生まれます", "animal_product": "グループコンサル型・少人数サロンなど、場作り商品が◎", "animal_sales": "押さず引かずの絶妙なバランスセールス。長期信頼型", "animal_mind": "「嫌われたくない」を緩め、断る勇気を持つと利益率が上がります", "animal_system": "人脈管理ツール（CRM）を入れると、あなたの強みが10倍活きます", "animal_overall": "人とのご縁から新しいビジネスチャンスが次々舞い込む時期"},
    "コアラ":  {"traits_short": "静かな戦略家型", "animal_shukaku": "緻密な導線設計型。ブログ・メルマガの資産型集客が最強", "animal_product": "緻密に練られた段階設計（フロント→ミドル→バック）で安定収益化", "animal_sales": "データと実績で静かに説得する論理型セールス", "animal_mind": "「十分に練ってから」を手放し、70%ローンチを意識するだけで加速", "animal_system": "仕組み化の才能を最大限発揮するフェーズ。全工程の標準化が吉", "animal_overall": "属人化を脱し、仕組みで回る事業体へ変容する重要な時期"},
    "ゾウ":   {"traits_short": "コツコツ積み上げる信頼型", "animal_shukaku": "継続型の情報発信が最強。毎日更新ブログ・メルマガが資産化", "animal_product": "長期継続プログラム・年間契約など、息の長い商品が相性◎", "animal_sales": "これまでの積み上げと実績で自然と選ばれるタイプ", "animal_mind": "「地道すぎる」と自分を過小評価せず、継続力こそ最大の才能と知って", "animal_system": "自動ステップメール・エバーグリーンウェビナーで積上資産を24時間稼働", "animal_overall": "10年続く強固な事業の基盤ができあがる重要な時期"},
    "ひつじ":  {"traits_short": "仲間と共に歩むチーム型", "animal_shukaku": "コミュニティ内での口コミ集客が強力。紹介制度を設計すると◎", "animal_product": "グループプログラム・仲間と進む伴走型商品が大得意", "animal_sales": "お客様の声・事例で自然と選ばれるソーシャルセールス", "animal_mind": "「仲間に申し訳ない」を緩めると、適正価格をつけられます", "animal_system": "コミュニティ運営を仕組み化するとあなたの時間が倍増します", "animal_overall": "仲間とのコラボ・共同事業で新しい展開が生まれる時期"},
    "ペガサス": {"traits_short": "自由奔放な天才型", "animal_shukaku": "既存の型にとらわれない独自発信で一気にバズる可能性大", "animal_product": "直感で生まれるユニーク商品・ぶっ飛び企画が当たります", "animal_sales": "エネルギーとインスピレーションで相手を魅了する感性セールス", "animal_mind": "「普通のビジネスは合わない」を肯定し、自分の型を作りましょう", "animal_system": "雑務は徹底外注。あなたは発想と創造に特化する体制が最大化のカギ", "animal_overall": "独自路線でブランド化し、唯一無二のポジションを取るフェーズ"},
}

GOGYO_MESSAGES = {
    "集客": {
        "木": "{name}さんの五行「木」は成長と発信のエネルギー。ブログ・動画・SNSに種まきを続けると半年後に指数関数的に伸びる資産型集客が合います。",
        "火": "{name}さんの五行「火」は熱量と表現の塊。ライブ配信・セミナー・ローンチなど「熱が伝わる場」で圧倒的な集客力を発揮します。",
        "土": "{name}さんの五行「土」は信頼と継続のエネルギー。毎日の発信・顧客の声の積み重ねで、じわじわ広がる口コミ集客が最強です。",
        "金": "{name}さんの五行「金」は価値と選別のエネルギー。万人ウケを狙わず「刺さる一部の人」に全振りするコピーと導線設計が集客を決めます。",
        "水": "{name}さんの五行「水」は共鳴と浸透のエネルギー。共感型のストーリー発信・音声配信で深いファンが育つタイプです。",
    },
    "商品設計": {
        "木": "{name}さんの五行「木」は段階的成長の象徴。初級→中級→上級と階段状に学びを提供する商品設計が顧客の成果と単価UPを両立させます。",
        "火": "{name}さんの五行「火」は短期集中の爆発力。3日・1週間・1ヶ月の短期集中プログラムで即効性のある変容を届けると高単価でも売れます。",
        "土": "{name}さんの五行「土」は基盤を作る力。6ヶ月〜1年の伴走型プログラムでクライアントに確実な成果を出す商品が一番の強み。",
        "金": "{name}さんの五行「金」は価値を結晶化する力。少人数マスターマインド・VIPコースなど、希少性と高単価を両立させる設計が最適。",
        "水": "{name}さんの五行「水」は流れと変容の力。定額サブスク・継続サロンなど、ゆるやかに長く寄り添う商品設計が相性抜群。",
    },
    "セールス": {
        "木": "五行「木」のあなたはクライアントの成長ストーリーを描くのが得意。Before/Afterと未来の姿を語ると、自然と成約が生まれます。",
        "火": "五行「火」のあなたは熱量で圧倒するクロージング型。ウェビナー・個別相談で情熱を伝えれば、高単価でも即決されます。",
        "土": "五行「土」のあなたは安心感で売るタイプ。丁寧なヒアリングと実績提示で、迷う人の背中を押す王道セールスが最強。",
        "金": "五行「金」のあなたは論理×価値提案型。投資対効果を数字で示す提案書スタイルが、経営者層にも響きます。",
        "水": "五行「水」のあなたは共感型セールスの天才。相手の本音を引き出すと、売り込まなくても選ばれます。",
    },
    "マインド": {
        "木": "五行「木」のあなたは「完璧な状態になってから」のブロックを解くと、発信量が3倍になります。種まきの時期に量は正義です。",
        "火": "五行「火」のあなたは「稼ぐ＝汚い」の呪いを外すと、本来の熱量がそのまま売上に転換されます。お金=感謝の具現化と捉え直して。",
        "土": "五行「土」のあなたは「自分はまだ実績が足りない」のブロックを解除。すでに十分な価値があることを受け取る訓練を。",
        "金": "五行「金」のあなたは「人に厳しくしたくない」の迷いを手放すと、適正価格と選別ができるようになります。",
        "水": "五行「水」のあなたは「お客様の感情を背負いすぎる」傾向。境界線を引く練習で、エネルギー漏れが止まります。",
    },
    "仕組み化": {
        "木": "五行「木」のあなたは「育てる仕組み」が得意。ステップメール・顧客育成ジャーニーを設計すると、見込み客が勝手に育ちます。",
        "火": "五行「火」のあなたは「情熱の再現」が鍵。ウェビナー録画を自動配信する仕組みで、寝ている間も成約が発生します。",
        "土": "五行「土」のあなたはマニュアル化・SOP化が天才的にうまい。今の業務を文書化するだけで、外注・チーム化が一気に進みます。",
        "金": "五行「金」のあなたは効率化・整理整頓の達人。ツール選定と導線最適化で、作業時間を半分にできます。",
        "水": "五行「水」のあなたは流れを作るのが得意。LINE公式・CRMで顧客ジャーニーを設計すると、自然な流れで契約が生まれます。",
    },
    "経営全体": {
        "木": "{name}さんの五行「木」は今、新規事業・新商品の芽が出る時期。小さく試して、育つものに集中投資する戦略が最適。",
        "火": "{name}さんの五行「火」は今、発信・露出が最大化する時期。出版・メディア・コラボなど表舞台に立つチャンスを掴みましょう。",
        "土": "{name}さんの五行「土」は今、基盤と仕組みが固まる重要な時期。派手さより、離脱率の低い強固な事業構造を作るフェーズ。",
        "金": "{name}さんの五行「金」は今、整理と選別の時期。不要な商品・クライアント・タスクを手放すと、一気に利益率が上がります。",
        "水": "{name}さんの五行「水」は今、ピボット・変容の時期。ペルソナ再定義と商品刷新で、次のステージへ飛躍できます。",
    },
}

COMPREHENSIVE_TEMPLATES = [
    "{name}さんは{sign}の{element_z}の経営エネルギーと、{animal_name}の{traits_short}な起業家タイプ、そして五行「{gogyo_el}」の{gogyo_nature}の力を併せ持つ、ユニークな経営者配置です。「{concern_cat}」に関しては3つの占術がすべて「仕組みと感性の両立」を示しています。感性を守りながら数字を追う、そのバランスが今あなたに必要なテーマ。属人労働から、感性が活きる仕組みへ。この転換こそ次のステージへの鍵です。",
    "{name}さんの3つの占術が見事に1つのメッセージを伝えています。{sign}の{ruler}は「自分の商品に堂々と価値をつけなさい」と、{animal_name}は「あなたらしい経営スタイルを貫きなさい」と、五行「{gogyo_el}」は「{gogyo_nature}の力をビジネスに活かしなさい」と語りかけています。「{concern_cat}」の壁は、感性起業家の次のステージへの通過儀礼。感性を売らず、仕組みで売上を上げる設計に切り替えるタイミングです。",
]

ADVICE_TEMPLATES = {
    "木": "🌱 「育てる」発想が吉：ステップメール・顧客育成ジャーニーの設計を\n📗 学びへの自己投資が半年後の売上に直結する時期\n🌿 朝のアイデアメモ習慣で、次の商品の種が降ります",
    "火": "🔥 「熱を伝える」場を増やす：ライブ配信・ウェビナー・個別相談\n🌅 朝一番に本日のコア発信を。勢いが数字を生む時期\n❤️ 情熱的な発信がそのままセールスになるので遠慮せず表現を",
    "土": "🏔️ 「基盤固め」に時間投資：SOP化・マニュアル化・資産化\n📝 顧客の声・事例の蓄積が最大の営業ツールになります\n🍠 地道なKPI追跡が、次の飛躍の土台になる時期",
    "金": "✨ 「整理と選別」の最強タイミング：不採算商品・タスクの断捨離\n🧹 ペルソナを1人に絞ると、単価と成約率が同時に上がります\n🔔 無駄を削ぎ落とすほど、利益率が劇的に改善します",
    "水": "💧 「流れを作る」時期：LINE導線・自動化で顧客ジャーニーを設計\n🌊 感性を活かした共感型メルマガが、深いファンを生みます\n🛁 休息を戦略的に取ることが、次のインスピレーションを呼びます",
}


def generate_reading_local(session):
    """テンプレートベースで即時鑑定テキスト生成"""
    name = session["name"]
    zodiac = session.get("zodiac", {})
    animal = session.get("animal", {})
    gogyo = session.get("gogyo", {})
    ei = gogyo.get("element_info", {})
    category = session.get("concern_category", "全体運")

    sign = zodiac.get("sign", "")
    element_z = zodiac.get("element", "")
    ruler = zodiac.get("ruler", "")
    animal_name = animal.get("name", "")
    gogyo_el = gogyo.get("element", "")
    gogyo_nature = ei.get("nature", "")

    ad = ANIMAL_DETAILS.get(animal_name, ANIMAL_DETAILS["狼"])

    # 西洋占星術メッセージ
    z_msgs = ZODIAC_MESSAGES.get(category, ZODIAC_MESSAGES["経営全体"]).get(element_z, ZODIAC_MESSAGES["経営全体"]["火"])
    if isinstance(z_msgs, list):
        western = random.choice(z_msgs)
    else:
        western = z_msgs
    western = western.format(name=name, sign=sign, ruler=ruler, element=element_z)

    # 動物占いメッセージ
    a_tpl = ANIMAL_MESSAGES.get(category, ANIMAL_MESSAGES["経営全体"])
    animal_msg = a_tpl.format(
        name=name, animal_name=animal_name,
        traits_short=ad["traits_short"],
        group=animal.get("group", ""),
        animal_shukaku=ad.get("animal_shukaku", ""),
        animal_product=ad.get("animal_product", ""),
        animal_sales=ad.get("animal_sales", ""),
        animal_mind=ad.get("animal_mind", ""),
        animal_system=ad.get("animal_system", ""),
        animal_overall=ad.get("animal_overall", ""),
    )

    # 算命術メッセージ
    g_msgs = GOGYO_MESSAGES.get(category, GOGYO_MESSAGES["経営全体"])
    gogyo_msg = g_msgs.get(gogyo_el, list(g_msgs.values())[0])
    gogyo_msg = gogyo_msg.format(name=name)

    # 総合メッセージ
    comp_tpl = random.choice(COMPREHENSIVE_TEMPLATES)
    comprehensive = comp_tpl.format(
        name=name, sign=sign, element_z=element_z, ruler=ruler,
        animal_name=animal_name, traits_short=ad["traits_short"],
        gogyo_el=gogyo_el, gogyo_nature=gogyo_nature,
        concern_cat=category,
    )

    # 開運アドバイス
    advice = ADVICE_TEMPLATES.get(gogyo_el, ADVICE_TEMPLATES["木"])

    return {
        "western": western,
        "animal": animal_msg,
        "gogyo": gogyo_msg,
        "comprehensive": comprehensive,
        "advice": advice,
    }


# ─── 鑑定結果 Flex Message ────────────────────────────────────
def _make_section_box(title, subtitle, body_text, accent_color):
    return {
        "type": "box", "layout": "vertical",
        "contents": [
            {"type": "box", "layout": "horizontal",
             "contents": [
                 {"type": "text", "text": title, "weight": "bold", "size": "sm", "color": accent_color, "flex": 6},
                 {"type": "text", "text": subtitle, "size": "sm", "color": "#333333", "align": "end", "weight": "bold", "flex": 4},
             ], "alignItems": "center"},
            {"type": "text", "text": body_text or "...", "size": "xs", "color": "#555555", "wrap": True, "margin": "sm"},
        ], "margin": "lg",
    }

def make_divination_result_flex(session, parsed):
    zodiac = session.get("zodiac", {})
    animal = session.get("animal", {})
    gogyo = session.get("gogyo", {})
    ei = gogyo.get("element_info", {})

    return {
        "type": "flex",
        "altText": f"💎 {session['name']}さんの経営タイプ鑑定",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "💎 ANASTA 経営タイプ鑑定 💎", "weight": "bold", "size": "lg", "align": "center", "color": "#e8c44a"},
                    {"type": "text", "text": f"{session['name']} さん", "size": "md", "align": "center", "color": "#ffffff", "margin": "sm"},
                    {"type": "text", "text": f"{session['birthday']} | テーマ：{session.get('concern_category', '経営全体')}", "size": "xxs", "align": "center", "color": "#b3a0d0", "margin": "xs"},
                ], "backgroundColor": "#1a0b30", "paddingAll": "20px"},
            "body": {"type": "box", "layout": "vertical",
                "contents": [
                    _make_section_box(f"🌟 西洋占星術（戦略タイプ）", f"{zodiac.get('symbol', '')} {zodiac.get('sign', '')}", parsed.get("western", ""), "#5a2da0"),
                    {"type": "separator", "margin": "lg"},
                    _make_section_box(f"🐾 動物占い（起業家キャラ）", f"{animal.get('emoji', '')} {animal.get('name', '')}", parsed.get("animal", ""), "#2E7D32"),
                    {"type": "separator", "margin": "lg"},
                    _make_section_box(f"☯️ 五行（経営エネルギー）", f"{ei.get('emoji', '')} {ei.get('name', '')}", parsed.get("gogyo", ""), ei.get("color", "#795548")),
                    {"type": "separator", "margin": "lg"},
                    {"type": "box", "layout": "vertical", "margin": "lg",
                     "backgroundColor": "#f2ecff", "cornerRadius": "10px", "paddingAll": "14px",
                     "contents": [
                         {"type": "text", "text": "💫 総合メッセージ", "weight": "bold", "size": "sm", "color": "#c9a227"},
                         {"type": "text", "text": parsed.get("comprehensive", "") or "...", "size": "xs", "color": "#333333", "wrap": True, "margin": "sm"},
                     ]},
                    {"type": "separator", "margin": "lg"},
                    {"type": "box", "layout": "vertical", "margin": "lg",
                     "backgroundColor": "#fef9f0", "cornerRadius": "10px", "paddingAll": "14px",
                     "contents": [
                         {"type": "text", "text": "💎 次の一手アドバイス", "weight": "bold", "size": "sm", "color": "#c9a227"},
                         {"type": "text", "text": parsed.get("advice", "") or "...", "size": "xs", "color": "#555555", "wrap": True, "margin": "sm"},
                     ]},
                ], "paddingAll": "20px"},
            "footer": {"type": "box", "layout": "vertical", "paddingAll": "16px",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#5a2da0", "height": "sm",
                     "action": {"type": "postback", "label": "💎 個別経営コンサルを予約する",
                                "data": "action=start_booking", "displayText": "個別コンサルを予約したいです"}},
                    {"type": "text", "text": "※ 感性を守りながら売上を伸ばす個別相談", "size": "xxs", "color": "#aaaaaa", "align": "center", "margin": "sm"},
                ]},
        },
    }

# ─── イベントハンドラー ───────────────────────────────────────
def handle_event(event):
    user_id = event.get("source", {}).get("userId", "")
    reply_token = event.get("replyToken", "")
    event_type = event.get("type", "")

    if event_type == "follow":
        reply(reply_token, {
            "type": "text",
            "text": "✨ ANASTAへようこそ ✨\n"
                    "Business Consulting for\nSpiritual Entrepreneurs\n\n"
                    "感性と数字を繋ぐ、\nあなただけの経営タイプ鑑定を\nお届けします💎\n\n"
                    "「鑑定」と送るとスタート！",
        })
        return

    if event_type == "message" and event.get("message", {}).get("type") == "text":
        text = event["message"]["text"].strip()
        session = get_session(user_id)
        step = session["step"]

        if text in ["占い", "鑑定", "スタート", "最初から", "もう一度", "経営鑑定", "簡易鑑定"]:
            reset_session(user_id)
            session = get_session(user_id)
            session["step"] = "ask_name"
            reply(reply_token, {
                "type": "text",
                "text": "💎 ANASTA 簡易経営鑑定 💎\n\n"
                        "西洋占星術 × 動物占い × 五行\n"
                        "3つの占術から、あなたの\n"
                        "経営タイプを診断します🌙\n\n"
                        "感性と数字のバランスを\n整える経営戦略鑑定✨\n\n"
                        "まず、お名前（ニックネームでもOK）を\n"
                        "教えてください🔻",
            })
            return

        if text in ["予約", "個別鑑定", "相談", "経営相談"]:
            session["step"] = "booking_date"
            reply(reply_token, [
                {"type": "text", "text": "💎 個別経営コンサルのご予約を承ります✨\n\nご都合の良い日をお選びください"},
                make_date_picker_msg(),
            ])
            return

        if step == "ask_name":
            session["name"] = text
            session["step"] = "ask_birthday"
            reply(reply_token, {
                "type": "text",
                "text": f"{text}さん✨\nよろしくお願いします🌸\n\n"
                        "次に、生年月日を教えてください🎂\n"
                        "（経営タイプの算出に使います）\n\n"
                        "例: 1990年3月15日\n"
                        "（1990/3/15 でもOKです）",
            })

        elif step == "ask_birthday":
            parsed = parse_birthday(text)
            if parsed is None or not validate_birthday(*parsed):
                reply(reply_token, {
                    "type": "text",
                    "text": "🙏 ごめんなさい、読み取れませんでした。\n\n"
                            "「1990年3月15日」のように\n入力してくださいね✨",
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
            # 即時生成＆即時返信（API不要）
            parsed_reading = generate_reading_local(session)
            flex_msg = make_divination_result_flex(session, parsed_reading)
            reply(reply_token, flex_msg)
            print(f"[DIVINATION OK] user={user_id[:8]} name={session['name']}", flush=True)
            session["step"] = "done"

        elif step in ("generating", "done"):
            reply(reply_token, {
                "type": "text",
                "text": "💎 もう一度鑑定する場合は\n「鑑定」とお送りください✨\n\n"
                        "個別経営コンサルのご予約は\n「予約」と送ってください🌙",
            })

        else:
            reply(reply_token, {
                "type": "text",
                "text": "✨ ANASTA 簡易経営鑑定へようこそ💎\n\n"
                        "「鑑定」と送ると経営タイプ診断を開始します\n"
                        "「予約」で個別経営コンサルのご予約ができます🌙",
            })

    elif event_type == "postback":
        session = get_session(user_id)
        data = parse_qs(event["postback"]["data"])

        if "gender" in data:
            session["gender"] = data["gender"][0]
            session["step"] = "ask_category"
            reply(reply_token, make_category_quick_reply())

        elif "category" in data:
            session["concern_category"] = data["category"][0]
            session["step"] = "ask_concern"
            reply(reply_token, {
                "type": "text",
                "text": f"💎 「{data['category'][0]}」の経営テーマですね\n\n"
                        "具体的に今どんな状況・壁を\n感じていますか？\n\n"
                        "自由にお書きください✨\n（一言でも長文でもOK）\n\n"
                        "例：集客が停滞している／\n高単価商品の売り方がわからない　など",
            })

        elif "action" in data and data["action"][0] == "start_booking":
            session["step"] = "booking_date"
            reply(reply_token, [
                {"type": "text", "text": "💎 個別経営コンサルのご予約\nありがとうございます✨\n\nご都合の良い日をお選びください"},
                make_date_picker_msg(),
            ])

        elif "booking_date" in data:
            session["booking_date"] = data["booking_date"][0]
            session["step"] = "booking_time"
            reply(reply_token, make_time_picker_msg())

        elif "booking_time" in data:
            selected_time = data["booking_time"][0]
            booking_date = session.get("booking_date", "")
            user_name = session.get("name", "")
            if not booking_date:
                reply(reply_token, {"type": "text", "text": "🙏 もう一度「予約」と送ってください"})
                reset_session(user_id)
                return
            reply(reply_token, make_booking_confirm_flex(booking_date, selected_time, user_name))
            d = datetime.strptime(booking_date, "%Y-%m-%d")
            wd = WEEKDAY_JP[d.weekday()]
            display_date = f"{d.year}年{d.month}月{d.day}日（{wd}）"
            concern = session.get("concern_category", "")
            push_message(OWNER_USER_ID, {
                "type": "text",
                "text": f"📩 新しい個別経営コンサルの予約が入りました！\n\n"
                        f"👤 お名前: {user_name or '未入力'}\n"
                        f"💎 経営テーマ: {concern or '未入力'}\n"
                        f"📅 日時: {display_date}\n"
                        f"⏰ 時間: {selected_time}\n\n"
                        f"確認連絡をお願いします🙏",
            })
            print(f"[BOOKING] user={user_id[:8]} name={user_name} date={booking_date} time={selected_time}", flush=True)
            reset_session(user_id)

# ─── HTTP サーバー ────────────────────────────────────────────
def verify_signature(body, signature):
    hash_ = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
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
        print(f"[SIG] len={len(body)} sig={signature[:20] if signature else 'none'}...", flush=True)

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
                print(f"[EVENT] type={event.get('type')} userId={eid}", flush=True)
                handle_event(event)
        except Exception as e:
            import traceback
            print(f"[ERROR] {e}\n{traceback.format_exc()}", flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"💎 ANASTA Business Bot running on port {port}", flush=True)
    server.serve_forever()
