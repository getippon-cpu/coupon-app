import streamlit as st
import json
import re
import base64
import sqlite3
from datetime import datetime
from PIL import Image
from io import BytesIO
import google.generativeai as genai

# ===============================
# API
# ===============================
genai.configure(api_key=st.secrets.get("GEMINI_API_KEY"))

def get_model():
    models = genai.list_models()
    for m in models:
        if "generateContent" in str(m.supported_generation_methods):
            return m.name
    return None

# ===============================
# DB
# ===============================
DB_FILE = "coupons.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS coupons (
            id TEXT PRIMARY KEY,
            store TEXT,
            discount TEXT,
            category TEXT,
            quantity INTEGER,
            used INTEGER,
            expiry TEXT,
            note TEXT,
            image TEXT
        )
    """)
    conn.commit()
    conn.close()

def load_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM coupons")
    rows = c.fetchall()
    conn.close()

    return [{
        "id": r[0],
        "store": r[1],
        "discount": r[2],
        "category": r[3],
        "quantity": r[4],
        "used": r[5],
        "expiry": r[6],
        "note": r[7],
        "image": r[8]
    } for r in rows]

def save_item(item):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        INSERT OR REPLACE INTO coupons
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        item["id"],
        item["store"],
        item["discount"],
        item["category"],
        item["quantity"],
        item["used"],
        item["expiry"],
        item.get("note",""),
        item["image"]
    ))

    conn.commit()
    conn.close()

def delete_item(item_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM coupons WHERE id=?", (item_id,))
    conn.commit()
    conn.close()

# ===============================
# 画像
# ===============================
def to_b64(img):
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

def from_b64(b):
    return Image.open(BytesIO(base64.b64decode(b)))

# ===============================
# JSON
# ===============================
def safe_json(text):
    try:
        return json.loads(text)
    except:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except:
                pass
    return {}

# ===============================
# AI
# ===============================
def ai_extract(img):
    model = genai.GenerativeModel(get_model())

    prompt = """
この画像はクーポン券です。
以下を抽出してください：

- 店舗名
- 割引内容
- カテゴリ（飲食・物販・サービス・その他）
- 有効期限
- 備考

JSON形式で出力：
{
 "store": "",
 "discount": "",
 "category": "",
 "expiry": "",
 "note": ""
}
"""

    try:
        res = model.generate_content([prompt, img])
        return safe_json(res.text)
    except:
        return {}

# ===============================
# ★ 重要：画像をstateに保持
# ===============================
if "img" not in st.session_state:
    st.session_state.img = None

if "ocr" not in st.session_state:
    st.session_state.ocr = {}

def run_ai():
    if st.session_state.img is None:
        return
    result = ai_extract(st.session_state.img)
    st.session_state.ocr = result

# ===============================
# 初期化
# ===============================
init_db()

st.title("🎫 クーポン管理（完全修正版・安定版）")

# ===============================
# サイドバー
# ===============================
if st.sidebar.button("🧨 DBリセット"):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DROP TABLE IF EXISTS coupons")
    conn.commit()
    conn.close()
    init_db()
    st.rerun()

# ===============================
# 画像アップ（ここが重要）
# ===============================
file = st.file_uploader("画像アップ", type=["jpg","png","jpeg"])

if file:
    img = Image.open(file)
    st.session_state.img = img
    st.image(img)

# ===============================
# AIボタン（stateベース）
# ===============================
if st.button("🤖 AI解析"):
    run_ai()
    st.rerun()

ocr = st.session_state.ocr

# ===============================
# 入力
# ===============================
store = st.text_input("店舗名", ocr.get("store",""))
discount = st.text_input("割引", ocr.get("discount",""))
category = st.selectbox(
    "カテゴリ",
    ["飲食","物販","サービス","その他"]
)
quantity = st.number_input("枚数", 1, 100, 1)

expiry = st.date_input("期限")
note = st.text_area("備考", ocr.get("note",""))

# ===============================
# 保存
# ===============================
if st.button("保存"):
    save_item({
        "id": str(datetime.now().timestamp()),
        "store": store,
        "discount": discount,
        "category": category,
        "quantity": quantity,
        "used": 0,
        "expiry": str(expiry),
        "note": note,
        "image": to_b64(st.session_state.img) if st.session_state.img else None
    })
    st.rerun()

# ===============================
# 一覧
# ===============================
st.subheader("一覧")

data = load_data()

for item in data:
    st.write(f"### {item['store']}")
    st.write(item["discount"])
    st.write("期限:", item["expiry"])

    if item.get("image"):
        st.image(from_b64(item["image"]), width=120)

    st.divider()
