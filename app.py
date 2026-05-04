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
# Gemini API
# ===============================
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ===============================
# モデル取得（キャッシュ）
# ===============================
@st.cache_data
def get_model():
    try:
        models = genai.list_models()
        for m in models:
            if "generateContent" in str(m.supported_generation_methods):
                return m.name
    except:
        pass
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

    return [
        {
            "id": r[0],
            "store": r[1],
            "discount": r[2],
            "category": r[3],
            "quantity": r[4],
            "used": r[5],
            "expiry": r[6],
            "note": r[7],
            "image": r[8]
        }
        for r in rows
    ]

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
def resize_image(img, max_size=1024):
    img = img.copy()
    img.thumbnail((max_size, max_size))
    return img

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

# ===============================
# JSON
# ===============================
def safe_json(text):
    try:
        return json.loads(text)
    except:
        m = re.search(r"\{.*?\}", text, re.DOTALL)
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

    st.write("AI実行開始")  # 🔴 ログ

    if st.session_state.get("ai_running", False):
        st.warning("AI処理中です")
        return {}

    st.session_state["ai_running"] = True

    prompt = """
クーポン画像を解析してJSONのみ返してください。

{
  "store": "",
  "discount": "",
  "expiry": "YYYY-MM-DD",
  "note": ""
}

ルール:
- JSONのみ
"""

    try:
        model_name = get_model()

        if not model_name:
            st.error("モデル取得失敗")
            return {}

        model = genai.GenerativeModel(model_name)

        # 🔴 画像軽量化
        img = resize_image(img)

        response = model.generate_content([prompt, img])

        return safe_json(response.text)

    except Exception as e:
        st.error(f"AIエラー: {e}")
        return {}

    finally:
        st.session_state["ai_running"] = False

# ===============================
# 日付
# ===============================
def parse_date_safe(s):
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        if d.year < 2000:
            return None
        return d
    except:
        return None

# ===============================
# 初期化
# ===============================
init_db()

if "ocr_done" not in st.session_state:
    st.session_state["ocr_done"] = False

st.title("🎫 クーポン管理")

# ===============================
# アップロード
# ===============================
file = st.file_uploader("画像アップ")

img = None

if file:
    img = Image.open(file)
    st.image(img)

    if st.button("AI解析") and not st.session_state["ocr_done"]:
        st.session_state["ocr"] = ai_extract(img)
        st.session_state["ocr_done"] = True

ocr = st.session_state.get("ocr", {})

# ===============================
# 入力
# ===============================
ai_expiry = parse_date_safe(ocr.get("expiry", ""))

if ai_expiry:
    st.success(f"AI検出: {ai_expiry}")

store = st.text_input("店舗", ocr.get("store", ""))
discount = st.text_input("割引", ocr.get("discount", ""))
category = st.selectbox("カテゴリ", ["飲食", "物販", "サービス", "その他"])
quantity = st.number_input("枚数", 1, 100, 1)

expiry = st.date_input(
    "期限",
    value=ai_expiry if ai_expiry else datetime.today().date()
)

note = st.text_area("備考", ocr.get("note", ""))

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
        "image": to_b64(img)
    })
    st.session_state["ocr_done"] = False
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

    try:
        d = datetime.strptime(item["expiry"], "%Y-%m-%d").date()
        days = (d - today).days
    except:
        days = 999

    st.markdown(f"### {item['store']}")
    st.write(f"{item['discount']} / {item['category']}")
    st.write(f"期限: {item['expiry']}（残り{days}日）")
    st.write(f"{used}/{qty}")

    if item.get("image"):
        st.image(from_b64(item["image"]), width=120)

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("使用", key=f"use_{item['id']}"):
            if used < qty:
                item["used"] += 1
                save_item(item)
                st.rerun()

    with c2:
        if st.button("戻す", key=f"back_{item['id']}"):
            if used > 0:
                item["used"] -= 1
                save_item(item)
                st.rerun()

    with c3:
        if st.button("削除", key=f"del_{item['id']}"):
            delete_item(item["id"])
            st.rerun()

    st.divider()
