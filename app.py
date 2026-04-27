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
# API初期化
# ===============================
GEMINI_OK = False

try:
    api_key = st.secrets.get("GEMINI_API_KEY", None)

    if api_key:
        genai.configure(api_key=api_key)
        GEMINI_OK = True
    else:
        st.error("APIキー未設定")
except Exception as e:
    st.error(f"APIエラー: {e}")

# ===============================
# データ
# ===============================
DATA_FILE = "coupons.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===============================
# 画像 → Base64
# ===============================
def image_to_base64(img):
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()

def base64_to_image(b64):
    return Image.open(BytesIO(base64.b64decode(b64)))

# ===============================
# AI解析（安定版）
# ===============================
def ai_from_image(image):

    if not GEMINI_OK:
        st.error("AI使用不可")
        return None

    prompt = """
この画像はクーポンです。
以下の情報をJSON形式で出力してください。

{
 "store": "",
 "discount": "",
 "expiry": "YYYY-MM-DD"
}

JSONのみ出力。
"""

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")

        response = model.generate_content([prompt, image])

        raw = response.text

        st.text_area("AI生データ", raw, height=150)

        cleaned = re.sub(r"```json|```", "", raw).strip()

        data = json.loads(cleaned)

        return data

    except Exception as e:
        st.error(f"AI解析失敗: {e}")
        return None

# ===============================
# UI
# ===============================
st.title("🎫 クーポン管理")

file = st.file_uploader("画像アップ", type=["jpg","png","jpeg"])

image = None

if file:
    image = Image.open(file)
    st.image(image, use_container_width=True)

    if st.button("AI解析"):
        result = ai_from_image(image)
        if result:
            st.session_state["ocr"] = result

st.divider()

ocr = st.session_state.get("ocr", {})

store = st.text_input("店舗名", value=ocr.get("store",""))
discount = st.text_input("割引", value=ocr.get("discount",""))

expiry_default = datetime.today()
if ocr.get("expiry"):
    try:
        expiry_default = datetime.strptime(ocr["expiry"], "%Y-%m-%d")
    except:
        pass

expiry = st.date_input("期限", value=expiry_default)

if st.button("保存"):

    img_b64 = None
    if image:
        img_b64 = image_to_base64(image)

    data = load_data()

    data.append({
        "store": store,
        "discount": discount,
        "expiry": str(expiry),
        "image": img_b64
    })

    save_data(data)

    st.success("保存OK")
    st.rerun()

# ===============================
# 一覧
# ===============================
st.subheader("一覧")

data = load_data()
today = datetime.today().date()

for i, item in enumerate(data):

    exp_str = item.get("expiry","")
    store = item.get("store","不明")
    discount = item.get("discount","")

    try:
        exp = datetime.strptime(exp_str, "%Y-%m-%d").date()
        days = (exp - today).days
    except:
        days = 999

    if days < 0:
        st.error(f"{store}（期限切れ）")
    elif days < 7:
        st.warning(f"{store}（あと{days}日）")
    else:
        st.success(f"{store}（{exp_str}）")

    if item.get("image"):
        st.image(base64_to_image(item["image"]), width=200)

    st.write(discount)

    if st.button("削除", key=i):
        data.pop(i)
        save_data(data)
        st.rerun()

    st.divider()
