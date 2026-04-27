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

# ===============================
# 画像
# ===============================
def to_b64(img):
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

# ===============================
# AI
# ===============================
def ai_extract(img):
    model = genai.GenerativeModel(get_model())

    prompt = """
この画像はクーポン券です。
店舗名、割引内容、カテゴリ、期限、備考を抽出してください。

JSONで返してください：
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
        return json.loads(re.search(r"\{.*\}", res.text, re.DOTALL).group())
    except:
        return {}

# ===============================
# 初期化
# ===============================
init_db()

st.title("🎫 クーポン管理（AI安定版）")

# ===============================
# session_state
# ===============================
if "img" not in st.session_state:
    st.session_state.img = None

if "ocr" not in st.session_state:
    st.session_state.ocr = {}

# ===============================
# 画像アップ
# ===============================
file = st.file_uploader("画像アップ", type=["jpg","png","jpeg"])

if file:
    st.session_state.img = Image.open(file)
    st.image(st.session_state.img)

# ===============================
# ★ AIボタン（修正版：必ず反応する）
# ===============================
if st.button("🤖 AI解析"):

    if st.session_state.img is None:
        st.warning("画像を先にアップしてください")
    else:
        with st.spinner("解析中..."):
            result = ai_extract(st.session_state.img)
            st.session_state.ocr = result
            st.success("解析完了")
        st.rerun()

ocr = st.session_state.ocr

# ===============================
# 入力
# ===============================
store = st.text_input("店舗名", ocr.get("store",""))
discount = st.text_input("割引", ocr.get("discount",""))
category = st.selectbox("カテゴリ", ["飲食","物販","サービス","その他"])
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
    st.success("保存しました")
    st.rerun()

# ===============================
# 一覧（簡易）
# ===============================
st.subheader("一覧")

for item in load_data():
    st.write(item["store"])
    st.write(item["discount"])
    st.write(item["expiry"])
    st.divider()
