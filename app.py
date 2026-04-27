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
# API設定（安定化）
# ===============================
API_KEY = st.secrets.get("GEMINI_API_KEY")

if not API_KEY:
    st.error("GEMINI_API_KEYが設定されていません")
    st.stop()

genai.configure(api_key=API_KEY)

MODEL_NAME = "models/gemini-1.5-flash-latest"

def get_model():
    return MODEL_NAME

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

def reset_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS coupons")
    conn.commit()
    conn.close()

    init_db()

def load_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM coupons")
    rows = c.fetchall()
    conn.close()

    data = []
    for r in rows:
        data.append({
            "id": r[0],
            "store": r[1],
            "discount": r[2],
            "category": r[3],
            "quantity": r[4],
            "used": r[5],
            "expiry": r[6],
            "note": r[7],
            "image": r[8]
        })
    return data

def save_item(item):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        INSERT OR REPLACE INTO coupons
        (id, store, discount, category, quantity, used, expiry, note, image)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        item["id"],
        item["store"],
        item["discount"],
        item["category"],
        item["quantity"],
        item["used"],
        item["expiry"],
        item.get("note", ""),
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
# 画像処理
# ===============================
def to_b64(img):
    if img is None:
        return ""
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()

def from_b64(b):
    if not b:
        return None
    return Image.open(BytesIO(base64.b64decode(b)))

def rotate_b64(b64, angle):
    img = from_b64(b64)
    if img is None:
        return b64
    img = img.rotate(angle, expand=True)
    return to_b64(img)

# ===============================
# JSON安全化
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
# AI解析（安定版）
# ===============================
def ai_extract(img):
    model = genai.GenerativeModel(MODEL_NAME)

    prompt = """
必ずJSONのみを返してください。説明は禁止。

{
 "store": "",
 "discount": "",
 "expiry": "YYYY-MM-DD",
 "note": ""
}
"""

    try:
        res = model.generate_content([prompt, img])
        return safe_json(res.text.strip())
    except Exception as e:
        st.error(f"AI解析エラー: {e}")
        return {}

# ===============================
# 初期化
# ===============================
init_db()

st.title("🎫 クーポン管理（安定版）")

# ===============================
# サイドバー
# ===============================
st.sidebar.header("管理")

if st.sidebar.button("🧨 DB完全リセット（全削除）"):
    reset_db()
    st.session_state.clear()
    st.sidebar.success("DBを初期化しました")
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

if file:
    img = Image.open(file)
    st.image(img)

    if st.button("🤖 AI解析"):
        st.session_state["ocr"] = ai_extract(img)

ocr = st.session_state.get("ocr", {})

# ===============================
# 入力
# ===============================
store = st.text_input("店舗名", ocr.get("store", ""))
discount = st.text_input("割引", ocr.get("discount", ""))
category = st.selectbox("カテゴリ", ["飲食", "物販", "サービス", "その他"])
quantity = st.number_input("枚数", 1, 100, 1)
expiry = st.date_input("期限")
note = st.text_area("備考（任意）", ocr.get("note", ""))

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
        "image": to_b64(img) if img else ""
    })
    st.rerun()

# ===============================
# 一覧
# ===============================
st.subheader("一覧")

data = load_data()
today = datetime.today().date()

for item in data:

    if search and search not in item["store"]:
        continue
    if category_filter != "すべて" and item["category"] != category_filter:
        continue

    used = item["used"]
    qty = item["quantity"]
    remaining = qty - used

    try:
        if item["expiry"]:
            d = datetime.strptime(item["expiry"], "%Y-%m-%d").date()
            days = (d - today).days
        else:
            days = 999
    except:
        days = 999

    col1, col2 = st.columns([1, 3])

    # 画像
    with col1:
        if item.get("image"):
            st.image(from_b64(item["image"]), width=120)

            c1, c2 = st.columns(2)

            with c1:
                if st.button("↺", key=f"l_{item['id']}"):
                    item["image"] = rotate_b64(item["image"], 90)
                    save_item(item)
                    st.rerun()

            with c2:
                if st.button("↻", key=f"r_{item['id']}"):
                    item["image"] = rotate_b64(item["image"], -90)
                    save_item(item)
                    st.rerun()

    # 情報
    with col2:
        st.markdown(f"### {item['store']}")
        st.write(f"{item['discount']} / {item['category']}")
        st.write(f"📅 期限: {item['expiry']}")

        if days < 0:
            st.error("期限切れ")
        else:
            st.write(f"残り日数: {days}日")

        st.write(f"使用: {used} / {qty}（残り {remaining}）")

        if item.get("note"):
            st.info(f"📝 {item['note']}")

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
