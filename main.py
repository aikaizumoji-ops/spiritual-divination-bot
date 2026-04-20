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
        ("🧲", "お客様集め"), ("💎", "商品づくり"), ("🤝", "お申込み"),
        ("🧠", "心の整え方"), ("⚙️", "続く仕組み"), ("🌈", "お仕事全体"),
    ]
    return {
        "type": "text",
        "text": "✨ 今、一番向き合いたいテーマは？",
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
        "type": "flex", "altText": f"個別相談のご予約：{display_date} {time_slot}",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "vertical",
                "contents": [{"type": "text", "text": "✅ ご予約を受け付けました",
                    "weight": "bold", "size": "lg", "align": "center", "color": "#ffffff"}],
                "backgroundColor": "#5a2da0", "paddingAll": "16px"},
            "body": {"type": "box", "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "💎 個別相談（オンライン）",
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
    "お客様集め": {
        "火": [
            "{name}さんの{sign}は{ruler}の後押しで、発信する力と熱い想いが魅力のタイプ。SNSやライブ配信など「あなたの想いが伝わる場」がお客様との出会いの入り口に。自分の物語を素直に語ることが、そのまま誰かの心を動かします。",
            "{name}さんは火のエレメント。情熱とスピード感で動くタイプ。「ちゃんと準備してから」よりも「やりながら整える」方が、圧倒的に人に届きます。まずは1つ発信してみましょう。",
        ],
        "地": [
            "{name}さんの{sign}は{ruler}に守られたコツコツ型。お客様集めは「少しずつ積み上げる」のが最強。ブログや定期メールなど、後に残る形のものが中心戦略です。派手さよりも続けることが信頼に変わります。",
            "{name}さんは地のエレメント。じっくり応援してくれる人を育てる力が強み。一気に広げるより、半年〜1年かけて安定した出会いの流れを作るのがあなたに合っています。",
        ],
        "風": [
            "{name}さんの{sign}は{ruler}の影響で、発想力と言葉にする力が光るタイプ。XやThreadsなど「言葉」で広がる場との相性がとても良いです。切り口の面白さで差をつけましょう。",
            "{name}さんは風のエレメント。流行を掴む感度と軽やかさが武器。対談やコラボなど「人との繋がりを広げる」やり方で、一気に知ってもらえる時期です。",
        ],
        "水": [
            "{name}さんの{sign}は{ruler}の深い感受性で、相手が言葉にしていない気持ちまで感じ取れるタイプ。「心に響く言葉」を書ける人です。たった一人に向けて書いたメッセージこそが、多くの人に届きます。",
            "{name}さんは水のエレメント。共感と癒しの世界観が最強の魅力。動画・音声・手紙のような温度のあるメルマガなど、じんわり伝わる媒体で深いファンが生まれます。",
        ],
    },
    "商品づくり": {
        "火": ["{name}さんの{sign}は{ruler}の力で、決断が早いパワータイプ。「本気で変わりたい人向けの、短期集中で結果を出す商品」が合います。価格にも自信を持って、堂々と打ち出して大丈夫。"],
        "地": ["{name}さんの{sign}は{ruler}守護の安定派。3ヶ月〜1年じっくり寄り添うプログラムや、ステップを分けた商品（お試し→本命）で安心感ある形が作れます。分割でのお支払いも喜ばれます。"],
        "風": ["{name}さんの{sign}は{ruler}の知的なエネルギーで、独自の切り口を言葉にする力が武器。商品の名前やキャッチコピーにこだわるほど、価格を上げても選ばれる人になります。"],
        "水": ["{name}さんの{sign}は{ruler}の深い感受性で、お客様の変化に寄り添う商品が最強。1対1のセッションや、少人数のグループなど、じっくり向き合える形が一番成果に繋がります。"],
    },
    "お申込み": {
        "火": ["{name}さんの{sign}は熱量で人の心を動かすタイプ。個別相談やオンラインセミナーなど「対話の熱」で選んでもらう場面で本領発揮。「いかがですか？」と一歩踏み込む勇気が大切です。"],
        "地": ["{name}さんの{sign}は誠実さと実績で信頼されるタイプ。Before/Afterの事例やお客様の声を丁寧に見せることで、迷っている人の背中をそっと押すことができます。"],
        "風": ["{name}さんの{sign}は分かりやすい説明で納得してもらえるタイプ。「この商品で得られる未来」を言葉にできれば、価格が高めでも安心して選んでもらえます。"],
        "水": ["{name}さんの{sign}は共感で選ばれるタイプ。相手の本音を引き出す「聴く力」が最大の武器。「売る」のではなく「一緒に未来を見る」姿勢が、お申込みへと自然に繋がります。"],
    },
    "心の整え方": {
        "火": ["{name}さんの{sign}は本来エネルギッシュに動けるタイプ。でも「お金をいただくのは悪いこと」という思い込みが足を止めることがあります。お金=感謝の形と捉え直すと、動き出せます。"],
        "地": ["{name}さんの{sign}は慎重さゆえに「まだ準備が足りない」と足踏みしがち。完璧を手放して「7割できたら出してみる」を合言葉に。動くほどに自信が育ちます。"],
        "風": ["{name}さんの{sign}は考えすぎて動けなくなる傾向があります。「感性を信じる＝先に答えが見えている」と理解すると、直感で決めても大丈夫と思えるようになります。"],
        "水": ["{name}さんの{sign}は人の気持ちを受け取りすぎて疲れやすいタイプ。「価格を上げる罪悪感」や「断る罪悪感」を手放すことが最優先。自分を満たすことが、実は一番の近道です。"],
    },
    "続く仕組み": {
        "火": ["{name}さんの{sign}は瞬発力が武器ですが、一人で抱えがち。自動で届くメルマガやLINEの自動メッセージで「寝ている間もお客様に出会える流れ」を作ると次のステージへ進めます。"],
        "地": ["{name}さんの{sign}はもともと仕組みを作る才能あり。自分の作業をマニュアルにしたり、一部をお願いするだけで、自由時間が3割増え、結果として売上も伸びる配置です。"],
        "風": ["{name}さんの{sign}はツール選びや情報整理が得意。NotionやAIなどの便利ツールを組み合わせれば、裏側の作業が半分になるタイミングに来ています。"],
        "水": ["{name}さんの{sign}は感性型ゆえに「仕組み化＝冷たい」と感じがち。でも仕組みがあるからこそ、お客様に丁寧に向き合う時間が生まれます。まずはLINEの自動挨拶からで十分です。"],
    },
    "お仕事全体": {
        "火": ["{name}さんの{sign}は今、広がりのエネルギーがとても高まっている時期。{ruler}の後押しで、思い切った挑戦が良い結果を生みます。同時に「一人で全部抱えない」工夫を進めると最高の流れに。"],
        "地": ["{name}さんの{sign}は今、土台がしっかり固まる時期。{ruler}のサポートで、安定して続く収入の流れが整います。派手な成長ではなく、ずっと応援してくれるお客様基盤を作るタイミング。"],
        "風": ["{name}さんの{sign}は今、新しい形の仕事が降りてくる時期。{ruler}の影響で、出会いや情報・コラボから「こういう方向もあるかも」のヒントが届きます。学びへの投資が加速させます。"],
        "水": ["{name}さんの{sign}は今、深い変化のタイミング。{ruler}があなたの感性を磨き、本当に届けたい相手がはっきり見えてきます。一人に絞る勇気が飛躍のカギです。"],
    },
}

# 旧カテゴリ辞書は削除済み

ANIMAL_MESSAGES = {
    "お客様集め": "{name}さんのタイプは「{animal_name}」。{traits_short}な人です。お客様との出会い方は{animal_shukaku}。{group}のエネルギーが発信スタイルを後押ししてくれます。",
    "商品づくり": "{name}さんのタイプは「{animal_name}」。{traits_short}な人です。商品づくりでは{animal_product}。{group}らしい形が一番ぴったり合います。",
    "お申込み": "{name}さんのタイプは「{animal_name}」。{traits_short}な人です。お申込みをいただく場面では{animal_sales}。{group}の持ち味がそのまま活きます。",
    "心の整え方": "{name}さんのタイプは「{animal_name}」。{traits_short}な人です。心の整え方では{animal_mind}。{group}の傾向を知ると、ふっと軽くなります。",
    "続く仕組み": "{name}さんのタイプは「{animal_name}」。{traits_short}な人です。仕組みづくりでは{animal_system}。{group}の特性を先回りで活かすのがコツ。",
    "お仕事全体": "{name}さんのタイプは「{animal_name}」。{traits_short}な人です。今のフェーズは{animal_overall}。{group}の強みを信じて進んでください。",
}

ANIMAL_DETAILS = {
    "狼":     {"traits_short": "マイペースで本質を追いかける", "animal_shukaku": "少数の深いファンを育てるタイプ。あなたの世界観をしっかり伝える濃いコンテンツが刺さります", "animal_product": "1対1のじっくり向き合う商品、特別感のあるコースが得意分野", "animal_sales": "多くは語らず、核心を突く質問で相手に気づきを与えるスタイルが活きます", "animal_mind": "「人に頼るのは悪いこと」の思い込みを緩めると、仲間と進める道が開けます", "animal_system": "一人で抱え込まず、最初の一人の協力者をお迎えするのが大きな転機に", "animal_overall": "丁寧さと深さで選ばれる、唯一無二の専門家ポジションが最適です"},
    "こじか":  {"traits_short": "繊細で共感力が高く、癒しを届ける", "animal_shukaku": "想いをのせたストーリー発信、手紙のような温かいメルマガでファンが育ちます", "animal_product": "少人数のコミュニティや、安心して学べる3〜6ヶ月のプログラムがぴったり", "animal_sales": "押し売り感ゼロの優しい寄り添い型。丁寧にお話を聴くことで自然と選ばれます", "animal_mind": "「価値を受け取る罪悪感」を外すと、適正な価格をつけられるようになります", "animal_system": "完璧を目指さず、まずLINE公式の簡単な自動挨拶から始めてみて", "animal_overall": "安心と癒しの世界観で、ずっと応援してくれるお客様が増えていく時期"},
    "猿":     {"traits_short": "器用で明るく、人を楽しませる", "animal_shukaku": "複数のSNSを横断した多面的な発信が武器。短い動画との相性も抜群", "animal_product": "お試しから本命まで幅広く揃えて、入り口を作るのが上手", "animal_sales": "楽しく軽やかな会話で選んでいただく、体験会・お茶会形式が得意", "animal_mind": "飽きやすさを受け入れて、半年ごとに新しい企画を生む前提で動くと楽になります", "animal_system": "ツール好きを活かして、AIや便利アプリで一気に楽になれる時期", "animal_overall": "いろんな切り口を活かして、複数の収入の流れを作れる配置"},
    "チータ":  {"traits_short": "瞬発力と勢いで動く行動派", "animal_shukaku": "期間限定キャンペーンや、お知らせ期間を設けた集め方が大得意", "animal_product": "3日〜1週間の集中プログラムなど、スピード感ある商品があなたに合います", "animal_sales": "勢いと直感で「今が決めどき」と背中を押すスタイルが活きます", "animal_mind": "「続けられない」を手放して、勢いで走り続ける作戦に切り替えましょう", "animal_system": "勢いを保つため、繰り返しの作業は早めに手放す・自動化するのが吉", "animal_overall": "短い企画を年に数回打って盛り上げる、メリハリ型のやり方が最適"},
    "黒ひょう": {"traits_short": "美意識が高く、感性で魅せる", "animal_shukaku": "ビジュアルと世界観で差別化。InstagramやYouTubeが主戦場になります", "animal_product": "特別感と芸術性のある商品づくりで、価格を上げても選ばれる存在に", "animal_sales": "感性で響き合う人を引き寄せるタイプ。数より質で選ばれます", "animal_mind": "「ビジネス＝野暮ったい」の思い込みを手放すと、美しく豊かになれる道が見えます", "animal_system": "創作する時間を守るため、事務的な作業は早めに手放しましょう", "animal_overall": "唯一無二のブランドを確立して、ファンに愛される存在になる転機"},
    "ライオン": {"traits_short": "堂々とした頼られるリーダー", "animal_shukaku": "実績や体験談で集める王道スタイル。出版・登壇・コラボが強力に効きます", "animal_product": "特別なプレミアム商品や、仲間を育てるコミュニティ主催がぴったり", "animal_sales": "説得力のあるお話で大きな決断をサポートする力あり。セミナーで本領発揮", "animal_mind": "「完璧な先生でなきゃ」を緩めると、等身大で豊かになれる楽さが来ます", "animal_system": "仲間を増やし、あなたは発信に専念する形が大きく伸ばすカギ", "animal_overall": "大きく広げるフェーズ。後輩を育てることも運気を上げてくれます"},
    "虎":     {"traits_short": "面倒見が良くて情に厚い", "animal_shukaku": "仲間を集めてコミュニティを作るのが強力。紹介からの出会いが最大チャネル", "animal_product": "じっくり伴走する長期プログラム（半年〜1年）と相性抜群", "animal_sales": "相手の人生に本気で向き合う熱い想いで、信頼で選ばれるタイプ", "animal_mind": "「全員を救わなきゃ」を手放すと、理想のお客様だけに絞れるようになります", "animal_system": "仲間に一部を任せられるようになると、あなたの自由時間が増えます", "animal_overall": "仲間との繋がりから、新しい展開が次々生まれる時期"},
    "たぬき":  {"traits_short": "場を和ませる調整上手", "animal_shukaku": "対談やコラボが得意。横の繋がりから自然と紹介が生まれます", "animal_product": "少人数のグループや、集まれる場所づくり系の商品が◎", "animal_sales": "押さず引かずの絶妙なバランスで、じっくり信頼関係を育てるタイプ", "animal_mind": "「嫌われたくない」を緩めて、ときには断る勇気を持つと楽になります", "animal_system": "お客様情報を整理する仕組みを入れると、あなたの強みが何倍にも活きます", "animal_overall": "人との繋がりから、新しいお仕事のチャンスが次々舞い込む時期"},
    "コアラ":  {"traits_short": "のんびりに見えて実は緻密な戦略家", "animal_shukaku": "丁寧な導線設計が得意。ブログやメルマガで長く残る資産を作るのが最強", "animal_product": "お試し→本命へと段階的に進める設計で、安定した流れを作れます", "animal_sales": "事例やデータで静かに納得してもらう、落ち着いたスタイル", "animal_mind": "「十分に練ってから」を手放して、7割でまず出してみると加速します", "animal_system": "仕組みを作る才能が最大限発揮される時期。手順の標準化がとても吉", "animal_overall": "自分一人でやる状態から、仕組みで回る形へ変わる大切な時期"},
    "ゾウ":   {"traits_short": "コツコツ積み上げる信頼の人", "animal_shukaku": "続けることが最強の武器。毎日の発信が少しずつ資産になっていきます", "animal_product": "長く続くプログラムや年間契約など、息の長い商品が相性◎", "animal_sales": "これまでの積み重ねと実績で、自然と選ばれるタイプ", "animal_mind": "「地道すぎる」と自分を小さく見ず、続ける力こそが最大の才能だと知って", "animal_system": "自動で届くメルマガなど、積み上げた資産を24時間働かせる仕組みが吉", "animal_overall": "10年先まで続く、しっかりした土台ができあがる重要な時期"},
    "ひつじ":  {"traits_short": "仲間思いで、みんなで進みたい", "animal_shukaku": "コミュニティ内での口コミが強力。紹介の仕組みを作るととても活きます", "animal_product": "仲間と進める伴走型のグループプログラムが大得意", "animal_sales": "お客様の声や体験談で、自然に選ばれるタイプ", "animal_mind": "「仲間に申し訳ない」を緩めると、適正な価格をつけられます", "animal_system": "コミュニティ運営を仕組み化すると、あなたの時間が倍増します", "animal_overall": "仲間とのコラボや共同企画から、新しい展開が生まれる時期"},
    "ペガサス": {"traits_short": "自由奔放で天才肌", "animal_shukaku": "既存の型にとらわれない独自の発信で、一気に広がる可能性大", "animal_product": "直感から生まれるユニークな企画・ぶっ飛んだアイデアが当たります", "animal_sales": "エネルギーと感性で相手を惹きつける直感型タイプ", "animal_mind": "「普通のやり方は合わない」を肯定して、自分なりの型を作りましょう", "animal_system": "雑務は思い切って手放し、発想と創造に集中する体制が伸びるカギ", "animal_overall": "独自路線でブランドを築き、唯一無二のポジションを取るフェーズ"},
}

GOGYO_MESSAGES = {
    "お客様集め": {
        "木": "{name}さんの五行「木」は育てていく力。ブログや動画・SNSで毎日少しずつ種をまき続けると、半年後にぐんと広がる資産型のやり方が合います。",
        "火": "{name}さんの五行「火」は熱量と表現の塊。ライブ配信やセミナー・お知らせ期間など「想いが伝わる場」で圧倒的な力を発揮します。",
        "土": "{name}さんの五行「土」は信頼と継続の力。毎日の発信・お客様の声の積み重ねで、じわじわ広がる口コミが最強です。",
        "金": "{name}さんの五行「金」は大切なものを見分ける力。みんなに好かれようとせず「本当に届けたい人」だけに向けた言葉が結果を生みます。",
        "水": "{name}さんの五行「水」は共鳴して伝わる力。共感ストーリーの発信や音声配信で、深いファンが育つタイプです。",
    },
    "商品づくり": {
        "木": "{name}さんの五行「木」は段階的に育つ象徴。入門→本命→上級と、階段のように進める商品づくりがあなたとお客様の両方に良いです。",
        "火": "{name}さんの五行「火」は短期集中の爆発力。3日・1週間・1ヶ月の短期プログラムで、すぐに変化を感じてもらえる商品が活きます。",
        "土": "{name}さんの五行「土」は土台を作る力。半年〜1年の伴走型プログラムで、お客様にしっかり変化を届ける商品が最大の強み。",
        "金": "{name}さんの五行「金」は本質を結晶にする力。少人数の特別なグループや限定コースなど、丁寧に向き合う商品が最適。",
        "水": "{name}さんの五行「水」は流れと変化の力。月額プランや続けるサロン形式など、ゆるやかに長く寄り添う商品が相性抜群。",
    },
    "お申込み": {
        "木": "五行「木」のあなたはお客様の成長ストーリーを描くのが得意。Before/Afterと未来の姿を語ると、自然と選ばれます。",
        "火": "五行「火」のあなたは熱量でグッと心を動かすタイプ。セミナーや個別相談で想いを伝えれば、価格が高めでも決まります。",
        "土": "五行「土」のあなたは安心感で選ばれるタイプ。丁寧な対話と実績の提示で、迷う人の背中を押す王道スタイルが最強。",
        "金": "五行「金」のあなたは分かりやすい価値提案が得意。「得られる結果」を数字で示せると、しっかり考える人にも響きます。",
        "水": "五行「水」のあなたは共感の天才。相手の本音を引き出すと、売り込まなくても選ばれます。",
    },
    "心の整え方": {
        "木": "五行「木」のあなたは「完璧になってから」の思い込みを外すと、発信量が3倍になります。今は種をまく時期、量を出すことが正解。",
        "火": "五行「火」のあなたは「お金をいただく＝悪いこと」の思い込みを手放すと、本来の熱量がそのまま収入になります。お金＝感謝の形と思い直して。",
        "土": "五行「土」のあなたは「私はまだ実績が足りない」の思い込みを外して。すでに十分な価値があることを、まず自分が受け取る練習を。",
        "金": "五行「金」のあなたは「人に厳しくしたくない」の迷いを手放すと、適正な価格や選び方ができるようになります。",
        "水": "五行「水」のあなたはお客様の感情を受けすぎがち。自分と相手の境界線をそっと引く練習で、疲れにくくなります。",
    },
    "続く仕組み": {
        "木": "五行「木」のあなたは「育てる仕組み」が得意。自動で順に届くメールでお客様を育てる形が、気づけば勝手に動く流れに。",
        "火": "五行「火」のあなたは「熱い想いを何度も届ける」のが鍵。オンラインセミナーの録画を自動配信すれば、寝ている間もお申込みが入ります。",
        "土": "五行「土」のあなたは手順を整えるのが天才的にうまい。今の作業を書き出すだけで、一部を誰かに任せられる段階に進めます。",
        "金": "五行「金」のあなたは効率化・整理整頓の達人。便利ツールを整えるだけで、作業時間が半分になります。",
        "水": "五行「水」のあなたは流れを作るのが得意。LINE公式やお客様管理の仕組みで、自然にご縁がつながる流れが作れます。",
    },
    "お仕事全体": {
        "木": "{name}さんの五行「木」は今、新しい挑戦や新商品の芽が出る時期。小さく試して、育ちそうなものに集中していくのが最適です。",
        "火": "{name}さんの五行「火」は今、発信・露出が最大化する時期。メディアやコラボなど、表に出るチャンスを積極的に掴みましょう。",
        "土": "{name}さんの五行「土」は今、土台と仕組みが固まる重要な時期。派手さよりも、ずっと続いていく強い形を作るフェーズ。",
        "金": "{name}さんの五行「金」は今、整理と選びの時期。合わなくなった商品やタスクを手放すと、一気に豊かになります。",
        "水": "{name}さんの五行「水」は今、方向転換と変容の時期。届けたい人や商品を見直すと、次のステージへ飛躍できます。",
    },
}

COMPREHENSIVE_TEMPLATES = [
    "{name}さんは{sign}の{element_z}のエネルギーと、{animal_name}の{traits_short}人柄、そして五行「{gogyo_el}」の{gogyo_nature}の力を併せ持つ、とても素敵な組み合わせです。「{concern_cat}」に関しては、3つの占術がすべて「感性と仕組みの両立」を示しています。感性を大切にしながら、続いていく仕組みを作る。そのバランスが今のあなたのテーマ。一人で頑張る状態から、感性が活きる形へ。この変化が次のステージへの鍵になります。",
    "{name}さんの3つの占術が見事に1つのメッセージを伝えています。{sign}の{ruler}は「自分の提供する価値に堂々と自信を持って」と、{animal_name}は「あなたらしいやり方を貫いて」と、五行「{gogyo_el}」は「{gogyo_nature}の力をお仕事に活かして」と語りかけています。「{concern_cat}」の壁は、感性を活かして働く人の次のステージへの入り口。感性を売らず、仕組みを味方につけて豊かになるタイミングです。",
]

ADVICE_TEMPLATES = {
    "木": "🌱 「育てる」意識が吉：自動で届くメールでお客様を育てる流れを作って\n📗 学びへの投資が半年後の成果に直結する時期\n🌿 朝のアイデアメモ習慣で、次の商品の種が降りてきます",
    "火": "🔥 「想いを伝える」場を増やして：ライブ配信・セミナー・個別相談\n🌅 朝一番に今日の大事な発信を。勢いが結果を生む時期\n❤️ 情熱的な発信がそのままお申込みに繋がるので、遠慮せず表現を",
    "土": "🏔️ 「土台づくり」に時間を：手順書や資料の整理が大きな資産に\n📝 お客様の声や体験談をコツコツ貯めると、最大の紹介ツールに\n🍠 地道な積み重ねが、次の飛躍の土台になる時期",
    "金": "✨ 「整理と選び直し」の絶好のタイミング：合わない商品やタスクを手放して\n🧹 届けたい人を一人に絞ると、価格も選ばれる率も同時に上がります\n🔔 無駄を減らすほど、豊かさが加速します",
    "水": "💧 「自然な流れをつくる」時期：LINEや自動化で心地よい流れを設計\n🌊 感性を活かした共感メルマガが、深いファンを生みます\n🛁 ゆったり休むことが、次のひらめきを呼び込みます",
}


def generate_reading_local(session):
    """テンプレートベースで即時鑑定テキスト生成"""
    name = session["name"]
    zodiac = session.get("zodiac", {})
    animal = session.get("animal", {})
    gogyo = session.get("gogyo", {})
    ei = gogyo.get("element_info", {})
    category = session.get("concern_category", "お仕事全体")

    sign = zodiac.get("sign", "")
    element_z = zodiac.get("element", "")
    ruler = zodiac.get("ruler", "")
    animal_name = animal.get("name", "")
    gogyo_el = gogyo.get("element", "")
    gogyo_nature = ei.get("nature", "")

    ad = ANIMAL_DETAILS.get(animal_name, ANIMAL_DETAILS["狼"])

    # 西洋占星術メッセージ
    z_msgs = ZODIAC_MESSAGES.get(category, ZODIAC_MESSAGES["お仕事全体"]).get(element_z, ZODIAC_MESSAGES["お仕事全体"]["火"])
    if isinstance(z_msgs, list):
        western = random.choice(z_msgs)
    else:
        western = z_msgs
    western = western.format(name=name, sign=sign, ruler=ruler, element=element_z)

    # 動物占いメッセージ
    a_tpl = ANIMAL_MESSAGES.get(category, ANIMAL_MESSAGES["お仕事全体"])
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
    g_msgs = GOGYO_MESSAGES.get(category, GOGYO_MESSAGES["お仕事全体"])
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
        "altText": f"💎 {session['name']}さんの鑑定結果",
        "contents": {
            "type": "bubble", "size": "mega",
            "header": {"type": "box", "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "💎 ANASTA 簡易鑑定結果 💎", "weight": "bold", "size": "lg", "align": "center", "color": "#e8c44a"},
                    {"type": "text", "text": f"{session['name']} さん", "size": "md", "align": "center", "color": "#ffffff", "margin": "sm"},
                    {"type": "text", "text": f"{session['birthday']} | テーマ：{session.get('concern_category', 'お仕事全体')}", "size": "xxs", "align": "center", "color": "#b3a0d0", "margin": "xs"},
                ], "backgroundColor": "#1a0b30", "paddingAll": "20px"},
            "body": {"type": "box", "layout": "vertical",
                "contents": [
                    _make_section_box(f"🌟 西洋占星術（あなたらしさ）", f"{zodiac.get('symbol', '')} {zodiac.get('sign', '')}", parsed.get("western", ""), "#5a2da0"),
                    {"type": "separator", "margin": "lg"},
                    _make_section_box(f"🐾 動物占い（働き方タイプ）", f"{animal.get('emoji', '')} {animal.get('name', '')}", parsed.get("animal", ""), "#2E7D32"),
                    {"type": "separator", "margin": "lg"},
                    _make_section_box(f"☯️ 五行（あなたのエネルギー）", f"{ei.get('emoji', '')} {ei.get('name', '')}", parsed.get("gogyo", ""), ei.get("color", "#795548")),
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
                     "action": {"type": "postback", "label": "💎 個別相談を予約する",
                                "data": "action=start_booking", "displayText": "個別相談を予約したいです"}},
                    {"type": "text", "text": "※ 感性を大切にしながら進める個別相談", "size": "xxs", "color": "#aaaaaa", "align": "center", "margin": "sm"},
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
                    "感性を大切にしながら、\n自分らしくお仕事を育てたい\nあなたのための場所です💎\n\n"
                    "3つの占いから、\nあなたらしい働き方タイプを\n鑑定します🌙\n\n"
                    "「鑑定」と送るとスタート！",
        })
        return

    if event_type == "message" and event.get("message", {}).get("type") == "text":
        text = event["message"]["text"].strip()
        session = get_session(user_id)
        step = session["step"]

        if text in ["占い", "鑑定", "スタート", "最初から", "もう一度", "簡易鑑定"]:
            reset_session(user_id)
            session = get_session(user_id)
            session["step"] = "ask_name"
            reply(reply_token, {
                "type": "text",
                "text": "💎 ANASTA 簡易鑑定 💎\n\n"
                        "西洋占星術 × 動物占い × 五行\n"
                        "3つの占いから、あなたの\n"
                        "働き方タイプをお伝えします🌙\n\n"
                        "感性を大切にしながら、\n自分らしく続けていくための\n鑑定です✨\n\n"
                        "まず、お名前（ニックネームでもOK）を\n"
                        "教えてください🔻",
            })
            return

        if text in ["予約", "個別鑑定", "相談"]:
            session["step"] = "booking_date"
            reply(reply_token, [
                {"type": "text", "text": "💎 個別相談のご予約を承ります✨\n\nご都合の良い日をお選びください"},
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
                        "（あなたのタイプを調べるために使います）\n\n"
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
                        "個別相談のご予約は\n「予約」と送ってください🌙",
            })

        else:
            reply(reply_token, {
                "type": "text",
                "text": "✨ ANASTA 簡易鑑定へようこそ💎\n\n"
                        "「鑑定」と送るとタイプ診断を開始します\n"
                        "「予約」で個別相談のご予約ができます🌙",
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
                "text": f"💎 「{data['category'][0]}」のテーマですね\n\n"
                        "今どんなことに悩んでいますか？\n\n"
                        "自由にお書きください✨\n（一言でも長文でもOK）\n\n"
                        "例：なかなかお客様が増えない／\n自分の商品をどう伝えたらいいか分からない　など",
            })

        elif "action" in data and data["action"][0] == "start_booking":
            session["step"] = "booking_date"
            reply(reply_token, [
                {"type": "text", "text": "💎 個別相談のご予約\nありがとうございます✨\n\nご都合の良い日をお選びください"},
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
                "text": f"📩 新しい個別相談の予約が入りました！\n\n"
                        f"👤 お名前: {user_name or '未入力'}\n"
                        f"💎 テーマ: {concern or '未入力'}\n"
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
