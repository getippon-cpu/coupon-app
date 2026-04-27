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

@st.cache_data
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
        "image": r[7]
    } for r in rows]

def save_item(item):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO coupons VALUES (?,?,?,?,?,?,?,?)
    """, (
        item["id"],
        item["store"],
        item["discount"],
        item["category"],
        item["quantity"],
        item["used"],
        item["expiry"],
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
# 画像処理（回転機能追加）
# ===============================
def to_b64(img):
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

def from_b64(b):
    return Image.open(BytesIO(base64.b64decode(b)))

def rotate_image(img, angle):
    return img.rotate(angle, expand=True)

# ===============================
# JSON安全
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
# 初期化
# ===============================
init_db()

st.title("🎫 クーポン管理（回転・期限強化版）")

# ===============================
# アップロード
# ===============================
file = st.file_uploader("画像アップ", type=["jpg","png","jpeg"])

img = None

if file:
    img = Image.open(file)

    # ===========================
    # 🔄 手動回転UI（追加）
    # ===========================
    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅ 左回転"):
            img = rotate_image(img, 90)

    with col2:
        if st.button("➡ 右回転"):
            img = rotate_image(img, -90)

    st.image(img)

# ===============================
# 入力
# ===============================
store = st.text_input("店舗名")
discount = st.text_input("割引")
category = st.selectbox("カテゴリ", ["飲食","物販","サービス","その他"])
quantity = st.number_input("枚数", 1, 100, 1)
expiry = st.date_input("期限")

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
        "image": to_b64(img) if img else None
    })
    st.rerun()

# ===============================
# 一覧
# ===============================
st.subheader("一覧")

data = load_data()
today = datetime.today().date()

for item in data:

    used = item["used"]
    qty = item["quantity"]
    remaining = qty - used

    # 期限処理
    try:
        d = datetime.strptime(item["expiry"], "%Y-%m-%d").date()
        days = (d - today).days
    except:
        days = 999

    col1, col2 = st.columns([1, 3])

    with col1:
        if item.get("image"):
            st.image(from_b64(item["image"]), width=120)

    with col2:
        st.markdown(f"### {item['store']}")
        st.write(f"{item['discount']} / {item['category']}")

        # ===========================
        # ② 期限＋残日数（強化）
        # ===========================
        st.write(f"📅 期限: {item['expiry']}")

        if days < 0:
            st.error("期限切れ")
        else:
            st.write(f"残り日数: {days}日")

        st.write(f"使用状況: {used} / {qty}（残り {remaining}）")

        if qty > 0:
            st.progress(used / qty)

        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("使用", key=f"use_{item['id']}"):
                if item["used"] < item["quantity"]:
                    item["used"] += 1
                    save_item(item)
                    st.rerun()

        with c2:
            if st.button("戻す", key=f"back_{item['id']}"):
                if item["used"] > 0:
                    item["used"] -= 1
                    save_item(item)
                    st.rerun()

        with c3:
            if st.button("削除", key=f"del_{item['id']}"):
                delete_item(item["id"])
                st.rerun()

    st.divider()
