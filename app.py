import streamlit as st
import json
import os
from datetime import datetime
import re
from PIL import Image
import base64
import google.generativeai as genai
from io import BytesIO

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
# データ
# ===============================
DATA_FILE = "coupons.json"

def load_data():
    if os.path.exists(DATA_FILE):
        return json.load(open(DATA_FILE, encoding="utf-8"))
    return []

def save_data(data):
    json.dump(data, open(DATA_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

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
# AI
# ===============================
def ai_extract(img):

    model_name = get_model()
    model = genai.GenerativeModel(model_name)

    prompt = """
クーポン画像です。
以下をJSONで出力：

{
 "store":"",
 "discount":"",
 "expiry":"YYYY-MM-DD"
}

JSONのみ
"""

    res = model.generate_content([prompt, img])
    raw = res.text

    cleaned = re.sub(r"```json|```", "", raw).strip()

    try:
        return json.loads(cleaned)
    except:
        return {}

# ===============================
# UI
# ===============================
st.title("🎫 クーポン管理（完成版）")

file = st.file_uploader("画像アップ", type=["jpg","png","jpeg"])

img = None

if file:
    img = Image.open(file)
    st.image(img)

    if st.button("AI解析"):
        st.session_state["ocr"] = ai_extract(img)

ocr = st.session_state.get("ocr", {})

# 入力欄
store = st.text_input("店舗名", value=ocr.get("store",""))
discount = st.text_input("割引", value=ocr.get("discount",""))

# 追加項目
category = st.selectbox("カテゴリ", ["飲食","物販","サービス","その他"])
quantity = st.number_input("枚数", 1, 100, 1)

# 日付
exp_default = datetime.today()
if ocr.get("expiry"):
    try:
        exp_default = datetime.strptime(ocr["expiry"], "%Y-%m-%d")
    except:
        pass

expiry = st.date_input("期限", value=exp_default)

# 保存
if st.button("保存"):

    data = load_data()

    data.append({
        "store": store,
        "discount": discount,
        "category": category,
        "quantity": quantity,
        "expiry": str(expiry),
        "image": to_b64(img) if img else None
    })

    save_data(data)

    st.success("保存")
    st.rerun()

# ===============================
# 一覧
# ===============================
st.subheader("一覧")

data = load_data()
today = datetime.today().date()

for i, item in enumerate(data):

    store = item.get("store","不明")
    discount = item.get("discount","")
    category = item.get("category","")
    qty = item.get("quantity",1)
    exp = item.get("expiry","")

    try:
        d = datetime.strptime(exp,"%Y-%m-%d").date()
        days = (d - today).days
    except:
        days = 999

    if days < 0:
        st.error(f"{store}（期限切れ）")
    elif days < 7:
        st.warning(f"{store}（あと{days}日）")
    else:
        st.success(f"{store}（{exp}）")

    if item.get("image"):
        try:
            st.image(from_b64(item["image"]), width=200)
        except:
            pass

    st.write(f"""
カテゴリ: {category}  
枚数: {qty}  
割引: {discount}
""")

    if st.button("削除", key=i):
        data.pop(i)
        save_data(data)
        st.rerun()

    st.divider()
