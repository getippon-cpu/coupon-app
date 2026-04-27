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

def reset_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM coupons")
    conn.commit()
    conn.close()

# ===============================
# 画像処理
# ===============================
def to_b64(img):
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

def from_b64(b):
    return Image.open(BytesIO(base64.b64decode(b)))

def rotate_b64_image(b64, angle):
    img = from_b64(b64)
    img = img.rotate(angle, expand=True)
    return to_b64(img)

# ===============================
# JSON安全処理
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
# AI解析
# ===============================
def ai_extract(img):
    model_name = get_model()
    if not model_name:
        return {}

    model = genai.GenerativeModel(model_name)

    prompt = """
クーポン画像を解析しJSONで出力：

{
 "store":"",
 "discount":"",
 "expiry":"YYYY-MM-DD"
}
"""

    try:
        res = model.generate_content([prompt, img])
        return safe_json(res.text)
    except:
        return {}

# ===============================
# 初期化
# ===============================
init_db()

st.title("🎫 クーポン管理（完成版）")

# ===============================
# 管理
# ===============================
st.sidebar.header("管理")

if st.sidebar.button("⚠️ 全データ初期化"):
    reset_db()
    st.rerun()

# ===============================
# フィルタ
# ===============================
search = st.text_input("🔍 店名検索")

category_filter = st.selectbox(
    "カテゴリ",
    ["すべて", "飲食", "物販", "サービス", "その他"]
)

# ===============================
# アップロード
# ===============================
file = st.file_uploader("画像アップ", type=["jpg", "png", "jpeg"])

img = None
ocr = st.session_state.get("ocr", {})

if file:
    img = Image.open(file)

    st.image(img)

    # ===============================
    # AI解析（重要）
    # ===============================
    if st.button("🤖 AI解析", key="ai_extract"):
        st.session_state["ocr"] = ai_extract(img)

    ocr = st.session_state.get("ocr", {})

# ===============================
# 入力
# ===============================
store = st.text_input("店舗名", ocr.get("store",""))
discount = st.text_input("割引", ocr.get("discount",""))
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

    # フィルタ
    if search and search not in item["store"]:
        continue
    if category_filter != "すべて" and item["category"] != category_filter:
        continue

    used = item["used"]
    qty = item["quantity"]
    remaining = qty - used

    try:
        d = datetime.strptime(item["expiry"], "%Y-%m-%d").date()
        days = (d - today).days
    except:
        days = 999

    # ===============================
    # カードUI
    # ===============================
    col1, col2 = st.columns([1, 3])

    # -------------------------------
    # サムネイル＋回転（ここが今回の本体）
    # -------------------------------
    with col1:
        if item.get("image"):

            st.image(from_b64(item["image"]), width=120)

            r1, r2 = st.columns(2)

            with r1:
                if st.button("↺", key=f"rot_l_{item['id']}"):
                    item["image"] = rotate_b64_image(item["image"], 90)
                    save_item(item)
                    st.rerun()

            with r2:
                if st.button("↻", key=f"rot_r_{item['id']}"):
                    item["image"] = rotate_b64_image(item["image"], -90)
                    save_item(item)
                    st.rerun()

    # -------------------------------
    # 情報表示
    # -------------------------------
    with col2:
        st.markdown(f"### {item['store']}")
        st.write(f"{item['discount']} / {item['category']}")

        st.write(f"📅 期限: {item['expiry']}")

        if days < 0:
            st.error("期限切れ")
        else:
            st.write(f"残り日数: {days}日")

        st.write(f"使用: {used} / {qty}（残り {remaining}）")

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
