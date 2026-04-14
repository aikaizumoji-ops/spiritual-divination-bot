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
        "type": "flex", "altText": f"個別鑑定のご予約：{display_date} {time_slot}",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "vertical",
                "contents": [{"type": "text", "text": "✅ ご予約を受け付けました",
                    "weight": "bold", "size": "lg", "align": "center", "color": "#ffffff"}],
                "backgroundColor": "#5a2da0", "paddingAll": "16px"},
            "body": {"type": "box", "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "🔮 個別スピリチュアル鑑定",
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
    "恋愛": {
        "火": [
            "{name}さんの{sign}は{ruler}の守護のもと、情熱的で一途な愛情の持ち主。あなたの真っすぐな想いは、必ず相手の心に届きます。今は自分の直感を信じて、心が「いいな」と感じる方向へ一歩踏み出してみて。",
            "{name}さんの{sign}は火のエレメント。恋に対してストレートで、自分からアクションを起こせるパワーがあります。今の時期、自分を大切にすることで恋愛運もぐっと上昇するタイミングです。",
        ],
        "地": [
            "{name}さんの{sign}は{ruler}に守護された堅実な星座。じっくり関係を築いていくタイプなので、焦らなくて大丈夫。あなたの誠実さと安心感が、最高のパートナーを引き寄せます。",
            "{name}さんは地のエレメントの{sign}。安定した愛を育む力を持っています。今は自分磨きを楽しみながら、自然体でいることが最強の恋愛テクニックになります。",
        ],
        "風": [
            "{name}さんの{sign}は{ruler}の影響で知的で魅力的なコミュニケーション力が武器。会話を通じて深い絆が生まれるタイミングです。軽やかに、でも心を込めたメッセージが恋を動かすカギに。",
            "{name}さんは風のエレメント。自由で軽やかな恋愛観が魅力です。知的な刺激を共有できる相手とのご縁が、今まさに近づいています。",
        ],
        "水": [
            "{name}さんの{sign}は{ruler}の深い影響で、豊かな感受性と直感力が光ります。あなたの繊細な愛情表現こそが最大の魅力。相手の本音を感じ取る力で、より深い愛が育まれていきます。",
            "{name}さんは水のエレメント。深い愛情を持ち、相手に寄り添う力がとても強い人。その優しさを自分自身にも向けてあげることで、理想の恋愛が花開きます。",
        ],
    },
    "仕事": {
        "火": ["{name}さんの{sign}は{ruler}の後押しで、リーダーシップと行動力が際立つ時。新しいチャレンジが成功へつながる流れが来ています。直感を信じて動くことで、大きなチャンスを掴めるでしょう。"],
        "地": ["{name}さんの{sign}は{ruler}に守護された実務能力の持ち主。コツコツ積み重ねてきた努力が実を結ぶ時期。地に足のついたアプローチが周囲からの信頼をさらに高めます。"],
        "風": ["{name}さんの{sign}は{ruler}の影響で発想力とコミュニケーション力が武器。新しいアイデアや人脈が仕事の突破口になります。情報収集と発信を意識すると運気が加速します。"],
        "水": ["{name}さんの{sign}は{ruler}の深い洞察力が仕事に活きるタイミング。直感でピンときたことは正解のサイン。周囲のニーズを感じ取る力で、頼れる存在として評価が上がっています。"],
    },
    "人間関係": {
        "火": ["{name}さんの{sign}は明るいエネルギーで人を引きつける魅力の持ち主。今は本音で向き合うことで、より深い絆が生まれるタイミング。あなたの情熱的な姿に、周囲は自然と協力したくなります。"],
        "地": ["{name}さんの{sign}は安定感と誠実さが周囲に安心感を与えます。信頼関係をじっくり築くタイプのあなたこそ、長く続く本物のご縁に恵まれています。無理に合わせず、自分のペースを大切に。"],
        "風": ["{name}さんの{sign}は軽やかなコミュニケーション力で人の輪を広げる達人。多様な人との出会いが運気上昇のカギ。あなたの知的で楽しい会話が、周囲を明るく照らしています。"],
        "水": ["{name}さんの{sign}は共感力が高く、相手の気持ちに寄り添える優しさの持ち主。今は境界線を意識して、自分のエネルギーを守ることも大切。共感力は最大の才能です。"],
    },
    "金運": {
        "火": ["{name}さんの{sign}は直感的な金運センスの持ち主。今は「ワクワクすること」にお金を使うと、巡り巡って豊かさが返ってきます。大胆な投資よりも、自己成長への投資が吉。"],
        "地": ["{name}さんの{sign}は堅実な金運の持ち主。計画的にコツコツ貯蓄する力が光っています。今期は特に安定した収入の基盤を固めるチャンス。地道な努力が大きな実りになります。"],
        "風": ["{name}さんの{sign}は情報を活用した金運が好調。新しい収入源やスキルアップの機会にアンテナを張ってみて。人脈が金運アップのカギを握っています。"],
        "水": ["{name}さんの{sign}は直感で「流れ」を読む力に長けています。今は直感的に「良い」と感じるものに小さく投資してみましょう。感性を磨くことが結果的に金運アップにつながります。"],
    },
    "健康": {
        "火": ["{name}さんの{sign}は活動的なエネルギーが豊富。動きすぎてオーバーヒートしやすいので、適度な休息とクールダウンを意識して。朝のストレッチや散歩で、体内のリズムが整います。"],
        "地": ["{name}さんの{sign}は体質的にタフですが、溜め込みやすい傾向も。定期的なデトックスや自然の中でのリフレッシュが効果的。食事のバランスを少し意識するだけで体調が安定します。"],
        "風": ["{name}さんの{sign}は頭を使いすぎて神経が疲れやすい面があります。深呼吸や瞑想で「思考のリセット」を取り入れて。軽い運動で気の巡りを良くすることが健康運UPの秘訣。"],
        "水": ["{name}さんの{sign}は感受性が豊かな分、周囲のエネルギーを受けやすい体質。水に関わるリフレッシュ（入浴、水辺散歩）で浄化を意識すると、心身ともに軽くなります。"],
    },
    "全体運": {
        "火": ["{name}さんの{sign}は今、情熱のエネルギーが高まっている時期。新しいことを始めるのに最適なタイミングです。{ruler}の後押しで、自分を信じて進む先に大きな飛躍が待っています。"],
        "地": ["{name}さんの{sign}は今、着実に運気が上昇中。目の前のことに丁寧に取り組む姿勢が、大きな変化への土台を作っています。{ruler}のサポートで、安定した前進が期待できます。"],
        "風": ["{name}さんの{sign}は今、新しい風が吹き込んでいる時期。出会いや情報から人生を変えるヒントが届きます。{ruler}の影響で知的好奇心が高まっていますので、学びの姿勢を大切に。"],
        "水": ["{name}さんの{sign}は今、深い変容の時期。内側から湧き上がる直感を信じてください。{ruler}のエネルギーがあなたの感性を研ぎ澄ませ、魂が望む方向へ導いてくれています。"],
    },
}

ANIMAL_MESSAGES = {
    "恋愛": "{name}さんの動物キャラ「{animal_name}」は{traits_short}タイプ。恋愛でも{animal_love}。{group}のエネルギーが今、あなたの魅力を最大限に高めています。",
    "仕事": "{name}さんの動物キャラ「{animal_name}」は{traits_short}タイプ。仕事では{animal_work}。{group}のパワーが後押ししてくれています。",
    "人間関係": "{name}さんの「{animal_name}」は{traits_short}タイプ。人間関係では{animal_rel}。{group}の特性を活かすと、より心地よいご縁が広がります。",
    "金運": "{name}さんの「{animal_name}」は{traits_short}タイプ。お金との関係では{animal_money}。{group}のエネルギーを活かした行動が金運上昇のカギ。",
    "健康": "{name}さんの「{animal_name}」は{traits_short}タイプ。健康面では{animal_health}。{group}のリズムに合わせた生活で、心身のバランスが整います。",
    "全体運": "{name}さんの「{animal_name}」は{traits_short}タイプ。今の時期は{animal_general}。{group}のエネルギーが味方してくれています。",
}

ANIMAL_DETAILS = {
    "狼":     {"traits_short": "独立心が強くマイペースな実力派", "animal_love": "自分の世界を共有できる人との深い絆が生まれやすい時", "animal_work": "一人で集中できる環境が成果につながります", "animal_rel": "少数精鋭の深い付き合いが心地よいタイプ", "animal_money": "独自のセンスで賢い選択ができる時期", "animal_health": "一人の時間でリフレッシュすることが大切", "animal_general": "自分のペースを守ることで運気が安定"},
    "こじか":  {"traits_short": "純粋で繊細な感性の持ち主", "animal_love": "相手のちょっとした優しさに幸せを感じられる時期", "animal_work": "繊細な気配りが周囲から高く評価されます", "animal_rel": "心を許せる人との時間が安らぎになります", "animal_money": "堅実な管理が安心をもたらします", "animal_health": "心の安定が体調にも好影響を与えます", "animal_general": "安心できる居場所を大切にすると全体運UP"},
    "猿":     {"traits_short": "器用で社交的な人気者", "animal_love": "楽しい会話が恋のきっかけになりやすい時期", "animal_work": "持ち前の器用さでマルチタスクをこなせます", "animal_rel": "明るいムードメーカーとして周囲を和ませています", "animal_money": "アイデア次第で収入源が広がる時期", "animal_health": "好奇心を満たす活動がストレス解消に", "animal_general": "社交性を活かすと運気が大きく上昇"},
    "チータ":  {"traits_short": "スタートダッシュが得意な情熱家", "animal_love": "一目惚れ的なご縁が訪れる可能性大", "animal_work": "新しいプロジェクトで力を発揮できます", "animal_rel": "直感的に気の合う人との出会いが増えそう", "animal_money": "スピード感のある判断が良い結果に", "animal_health": "適度な運動で燃え尽きを防いで", "animal_general": "素早い決断と行動が幸運の扉を開きます"},
    "黒ひょう": {"traits_short": "感性豊かで美意識が高い人", "animal_love": "あなた独自の魅力に気づいてくれる人が現れる時", "animal_work": "クリエイティブな発想が周囲を驚かせます", "animal_rel": "本音で語り合える関係が一番の宝物", "animal_money": "美的センスを活かした選択が金運UP", "animal_health": "芸術や音楽でのリフレッシュが効果的", "animal_general": "自分の感性を信じると道が開けます"},
    "ライオン": {"traits_short": "堂々としたリーダー気質", "animal_love": "自然体のあなたに惹かれる人が増えています", "animal_work": "リーダーシップを発揮するチャンスが到来中", "animal_rel": "頼りにされることで絆が深まります", "animal_money": "スケールの大きな発想が金運を呼びます", "animal_health": "しっかり休むことも強さの一つ", "animal_general": "堂々と自分らしくいることが最強の開運法"},
    "虎":     {"traits_short": "正義感が強い親分肌", "animal_love": "面倒見の良さが相手の心を掴みます", "animal_work": "チームをまとめる力が評価される時期", "animal_rel": "困っている人を助けることでご縁が広がります", "animal_money": "人のために使うお金が巡り巡って戻ってきます", "animal_health": "責任を背負いすぎないよう注意", "animal_general": "義理人情を大切にすると運気好転"},
    "たぬき":  {"traits_short": "愛嬌があって人に好かれる調整役", "animal_love": "自然な笑顔が最高のモテ要素になっています", "animal_work": "調整力でプロジェクトが円滑に進みます", "animal_rel": "誰とでもうまく付き合える才能が光ります", "animal_money": "交際費が実は最良の投資になっている時期", "animal_health": "笑うことが一番の健康法", "animal_general": "周囲との調和を大切にすると全てがうまくいきます"},
    "コアラ":  {"traits_short": "のんびりに見えて実は戦略家", "animal_love": "ゆったりした雰囲気が相手に安心感を与えます", "animal_work": "緻密な計画力で成果を出すタイプ", "animal_rel": "リラックスした関係性を築ける力が魅力", "animal_money": "慎重な判断が確実な利益につながります", "animal_health": "十分な睡眠が運気全体を底上げ", "animal_general": "マイペースに、でも着実に進むことが大切"},
    "ゾウ":   {"traits_short": "努力家で粘り強い信頼の人", "animal_love": "誠実さが最高の魅力になっています", "animal_work": "コツコツ型の努力が大きな成果として実を結びます", "animal_rel": "長く付き合うほど信頼される存在", "animal_money": "地道な貯蓄と堅実な運用が金運安定のカギ", "animal_health": "無理をせず、ゆっくりペースが一番", "animal_general": "粘り強く続けることが最大の開運法"},
    "ひつじ":  {"traits_short": "仲間思いで情に厚い人", "animal_love": "人とのつながりの中から恋が生まれやすい時期", "animal_work": "チームワークの力で大きな成果を出せます", "animal_rel": "信頼できる仲間との絆が一番の財産", "animal_money": "グループでの活動が金運UPにつながります", "animal_health": "孤独は大敵。人と過ごす時間が元気の源", "animal_general": "大切な人との時間を優先すると運気UP"},
    "ペガサス": {"traits_short": "自由奔放な天才肌", "animal_love": "型にはまらない自由な恋愛観が魅力", "animal_work": "インスピレーションが降りてくる時期", "animal_rel": "自由を尊重し合える関係が心地よい", "animal_money": "直感的にピンときたものが当たりやすい時期", "animal_health": "気分転換の旅や冒険がエネルギー補給に", "animal_general": "自由に飛び回ることで運気が最大化"},
}

GOGYO_MESSAGES = {
    "恋愛": {
        "木": "{name}さんの五行は「木」。成長と発展のエネルギーが恋愛にも好影響。新しい出会いの芽がぐんぐん育つ時期です。自然体でいることが、最も美しいあなたを引き出します。",
        "火": "{name}さんの五行は「火」。情熱のエネルギーが恋愛を後押し。燃え上がる想いを素直に表現することで、理想の関係が築けます。直感を信じた行動が吉。",
        "土": "{name}さんの五行は「土」。安定と包容力のエネルギーが恋を支えます。焦らずじっくり育む愛が、一生続く関係になる予感。安心感を与えられるあなたは最高のパートナー。",
        "金": "{name}さんの五行は「金」。決断と浄化のエネルギーが恋愛の転機を告げています。必要のない関係を手放すことで、本物のご縁が入ってきます。",
        "水": "{name}さんの五行は「水」。柔軟で深い愛情が最大の魅力。相手に合わせる優しさは素晴らしいですが、自分の気持ちもしっかり伝えると関係がもっと深まります。",
    },
    "仕事": {
        "木": "{name}さんの五行「木」は成長と創造のエネルギー。今まさに新しいスキルや知識が枝葉のように広がる時期。学びへの投資が大きなリターンをもたらします。",
        "火": "{name}さんの五行「火」は表現と情熱のエネルギー。プレゼンや発信など「伝える」場面で力を発揮します。熱意は周囲を動かす最大の武器です。",
        "土": "{name}さんの五行「土」は安定と信頼のエネルギー。あなたの堅実さがチームの土台を支えています。今は基盤固めに集中すると、後々大きな飛躍につながります。",
        "金": "{name}さんの五行「金」は決断と実行のエネルギー。迷いを断ち切って行動に移すことで、停滞していた状況が一気に好転します。整理整頓も開運に。",
        "水": "{name}さんの五行「水」は知恵と柔軟性のエネルギー。状況に応じて変化できる適応力が武器。直感でキャッチした情報が仕事の突破口になります。",
    },
    "人間関係": {
        "木": "五行「木」のあなたは包容力で周囲を優しく包み込む人。成長を促すような関わりが、自然と良いご縁を引き寄せています。",
        "火": "五行「火」のあなたは情熱的で人を惹きつけるカリスマ性があります。温かいエネルギーで周囲を照らすことが、人間関係の好転につながります。",
        "土": "五行「土」のあなたは安定感があり、周囲に安心感を与えます。グラウンディングされたエネルギーが、信頼関係の基盤を強化しています。",
        "金": "五行「金」のあなたは凛とした存在感で尊敬を集めます。不要な関係を整理する勇気が、本当に大切な人との絆を深めます。",
        "水": "五行「水」のあなたは共感力が高く、相手の心に寄り添える人。その柔軟さが多くの人からの信頼を集めています。",
    },
    "金運": {
        "木": "五行「木」のエネルギーは成長・発展。種まきの時期です。今は学びや自己投資にお金を使うと、将来大きく育って返ってきます。",
        "火": "五行「火」のエネルギーは表現・発信。あなたの情熱をビジネスや副業に活かすと、予想以上の収入が生まれる可能性があります。",
        "土": "五行「土」のエネルギーは安定・蓄積。堅実な貯蓄と計画的な支出が金運の基盤。焦らずコツコツが最強の金運法です。",
        "金": "五行「金」のエネルギーは決断・浄化。無駄な出費を整理するだけで、金運が一気に好転します。質の良いものを選ぶ目が金運UP。",
        "水": "五行「水」のエネルギーは流れ・循環。お金は「流す」ことで増えるもの。感謝の気持ちを込めて使うと、豊かさの循環が生まれます。",
    },
    "健康": {
        "木": "五行「木」の健康は肝臓や筋肉と関連。ストレッチや森林浴など、伸びやかな動きが心身を整えます。グリーンの食材も◎。",
        "火": "五行「火」の健康は心臓や血液循環と関連。適度な有酸素運動と十分な休息のバランスが大切。赤い食材でエネルギーチャージ。",
        "土": "五行「土」の健康は消化器系と関連。食事のリズムと質を整えることが健康維持のカギ。大地の恵みの根菜類がおすすめ。",
        "金": "五行「金」の健康は呼吸器系と関連。深呼吸や瞑想で気の巡りを整えて。白い食材（大根、蓮根など）で体内浄化。",
        "水": "五行「水」の健康は腎臓やホルモンバランスと関連。十分な水分補給と良質な睡眠が最優先。温かい飲み物で体を温めて。",
    },
    "全体運": {
        "木": "{name}さんの五行「木」は今、成長のエネルギーに満ちています。新しいことを始めるなら今がベスト。小さな一歩が大きな変容のきっかけになります。",
        "火": "{name}さんの五行「火」は今、表現と行動のエネルギーが最高潮。自分の想いを外に発信することで、共鳴する人やチャンスが集まってきます。",
        "土": "{name}さんの五行「土」は今、着実に基盤が固まっている時期。目立たなくても、あなたの努力は確実に積み上がっています。信じて続けてください。",
        "金": "{name}さんの五行「金」は今、浄化と新生のタイミング。古いものを手放し、本当に大切なものだけに集中すると、人生が一気にクリアになります。",
        "水": "{name}さんの五行「水」は今、直感力が冴えわたる時期。論理よりも「なんとなく」を信じてみて。水のように柔軟に流れに身を任せることが開運法。",
    },
}

COMPREHENSIVE_TEMPLATES = [
    "{name}さんは{sign}の{element_z}のエネルギーと、{animal_name}の{traits_short}な性質、そして五行「{gogyo_el}」の{gogyo_nature}の力を併せ持つ、とてもユニークな星の配置です。{concern_cat}に関しては、3つの占術がすべて「今がまさに転機の時」と示しています。焦らず、でも確実に一歩ずつ前に進むことで、あなたの宇宙が応援してくれます。自分の心の声に耳を傾けて、直感が「YES」と言う方へ進んでください。",
    "{name}さんの3つの占術は見事に一つのメッセージを伝えています。{sign}の{ruler}は「自分を信じなさい」と、{animal_name}は「あなたらしくいなさい」と、五行「{gogyo_el}」は「{gogyo_nature}の力を活かしなさい」と語りかけています。{concern_cat}の悩みは、実はあなたの魂が次のステージへ進むためのサイン。この変容を恐れず受け入れることで、想像以上の素晴らしい未来が開けていきます。",
]

ADVICE_TEMPLATES = {
    "木": "🌿 朝、窓を開けて深呼吸する習慣で気の流れを整えましょう\n🌱 観葉植物を近くに置くと木のエネルギーが高まります\n📗 新しいことを1つ学び始めると成長運が加速します",
    "火": "🌅 朝日を浴びて一日をスタートさせましょう\n🕯 キャンドルの灯りで心を落ち着ける時間を\n❤️ 感謝の気持ちを言葉にして伝えると火のエネルギーが安定します",
    "土": "🚶 裸足で大地に触れるグラウンディングがおすすめ\n🍠 根菜類やオーガニック食材で体の中から安定を\n📝 日記を書いて思考を整理すると土のエネルギーが充実",
    "金": "✨ ゴールドやシルバーのアクセサリーが開運のお守りに\n🧹 部屋の整理整頓が金のエネルギーを活性化\n🔔 風鈴やクリスタルの澄んだ音で空間を浄化",
    "水": "💧 質の良い水をたくさん飲んでデトックスを\n🛁 入浴時に天然塩を入れてエネルギー浄化\n🌊 水辺に出かけて心をリフレッシュしましょう",
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
    z_msgs = ZODIAC_MESSAGES.get(category, ZODIAC_MESSAGES["全体運"]).get(element_z, ZODIAC_MESSAGES["全体運"]["火"])
    if isinstance(z_msgs, list):
        western = random.choice(z_msgs)
    else:
        western = z_msgs
    western = western.format(name=name, sign=sign, ruler=ruler, element=element_z)

    # 動物占いメッセージ
    a_tpl = ANIMAL_MESSAGES.get(category, ANIMAL_MESSAGES["全体運"])
    cat_map = {"恋愛": "animal_love", "仕事": "animal_work", "人間関係": "animal_rel",
               "金運": "animal_money", "健康": "animal_health", "全体運": "animal_general"}
    ak = cat_map.get(category, "animal_general")
    animal_msg = a_tpl.format(
        name=name, animal_name=animal_name,
        traits_short=ad["traits_short"],
        group=animal.get("group", ""),
        animal_love=ad.get("animal_love", ""),
        animal_work=ad.get("animal_work", ""),
        animal_rel=ad.get("animal_rel", ""),
        animal_money=ad.get("animal_money", ""),
        animal_health=ad.get("animal_health", ""),
        animal_general=ad.get("animal_general", ""),
    )

    # 算命術メッセージ
    g_msgs = GOGYO_MESSAGES.get(category, GOGYO_MESSAGES["全体運"])
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
        "altText": f"🔮 {session['name']}さんの鑑定結果",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "🔮✨ 総合鑑定結果 ✨🔮", "weight": "bold", "size": "lg", "align": "center", "color": "#e8c44a"},
                    {"type": "text", "text": f"{session['name']} さん", "size": "md", "align": "center", "color": "#ffffff", "margin": "sm"},
                    {"type": "text", "text": f"{session['birthday']} | {session['gender']}", "size": "xxs", "align": "center", "color": "#b3a0d0", "margin": "xs"},
                ], "backgroundColor": "#1a0b30", "paddingAll": "20px"},
            "body": {"type": "box", "layout": "vertical",
                "contents": [
                    _make_section_box(f"🌟 西洋占星術", f"{zodiac.get('symbol', '')} {zodiac.get('sign', '')}", parsed.get("western", ""), "#5a2da0"),
                    {"type": "separator", "margin": "lg"},
                    _make_section_box(f"🐾 動物占い", f"{animal.get('emoji', '')} {animal.get('name', '')}", parsed.get("animal", ""), "#2E7D32"),
                    {"type": "separator", "margin": "lg"},
                    _make_section_box(f"☯️ 算命術（五行）", f"{ei.get('emoji', '')} {ei.get('name', '')}", parsed.get("gogyo", ""), ei.get("color", "#795548")),
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
                         {"type": "text", "text": "🔮 開運アドバイス", "weight": "bold", "size": "sm", "color": "#c9a227"},
                         {"type": "text", "text": parsed.get("advice", "") or "...", "size": "xs", "color": "#555555", "wrap": True, "margin": "sm"},
                     ]},
                ], "paddingAll": "20px"},
            "footer": {"type": "box", "layout": "vertical", "paddingAll": "16px",
                "contents": [
                    {"type": "button", "style": "primary", "color": "#5a2da0", "height": "sm",
                     "action": {"type": "postback", "label": "🌙 もっと詳しく聞く（個別鑑定予約）",
                                "data": "action=start_booking", "displayText": "もっと詳しく聞きたいです"}},
                    {"type": "text", "text": "※ より深い個別鑑定のご予約ができます", "size": "xxs", "color": "#aaaaaa", "align": "center", "margin": "sm"},
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
            "text": "🔮 ようこそ✨\nスピリチュアル簡易鑑定へ\n\n"
                    "あらゆる占術を組み合わせて\n"
                    "あなただけの鑑定をお届けします🌙\n\n"
                    "「占い」と送ると鑑定スタート！",
        })
        return

    if event_type == "message" and event.get("message", {}).get("type") == "text":
        text = event["message"]["text"].strip()
        session = get_session(user_id)
        step = session["step"]

        if text in ["占い", "鑑定", "スタート", "最初から", "もう一度"]:
            reset_session(user_id)
            session = get_session(user_id)
            session["step"] = "ask_name"
            reply(reply_token, {
                "type": "text",
                "text": "🔮簡易鑑定を始めます🔮\n\n"
                        "あらゆる占術を組み合わせて\n"
                        "あなただけの鑑定結果をお届けします🌙\n\n"
                        "まず、お名前（ニックネームでもOK）を\n"
                        "教えてください🔻",
            })
            return

        if text in ["予約", "個別鑑定", "相談"]:
            session["step"] = "booking_date"
            reply(reply_token, [
                {"type": "text", "text": "🌙 個別鑑定のご予約を承ります✨\n\nご都合の良い日をお選びください"},
                make_date_picker_msg(),
            ])
            return

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
                "text": "🔮 もう一度鑑定する場合は\n「占い」とお送りください🌙\n\n"
                        "個別鑑定のご予約は「予約」で✨",
            })

        else:
            reply(reply_token, {
                "type": "text",
                "text": "🔮 スピリチュアル簡易鑑定へようこそ✨\n\n"
                        "「占い」と送ると鑑定を開始します🌙\n"
                        "「予約」で個別鑑定のご予約もできます✨",
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
                "text": f"🌙 {data['category'][0]}のお悩みですね\n\n"
                        "具体的にどんなことで\n悩んでいますか？\n\n"
                        "自由にお話しください✨\n（一言でも長文でもOKです）",
            })

        elif "action" in data and data["action"][0] == "start_booking":
            session["step"] = "booking_date"
            reply(reply_token, [
                {"type": "text", "text": "🌙 個別鑑定のご予約\nありがとうございます✨\n\nご都合の良い日をお選びください"},
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
                "text": f"📩 新しい個別鑑定の予約が入りました！\n\n"
                        f"👤 お名前: {user_name or '未入力'}\n"
                        f"🔮 お悩み: {concern or '未入力'}\n"
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
    print(f"🔮 Spiritual Bot running on port {port}", flush=True)
    server.serve_forever()
