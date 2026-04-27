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

# ===============================
# モデル取得（キャッシュ）
# ===============================
@st.cache_data
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
        data = json.load(open(DATA_FILE, encoding="utf-8"))

        # 旧データ救済（idがない場合）
        for i, item in enumerate(data):
            if "id" not in item:
                item["id"] = f"legacy_{i}"

            if "used" not in item:
                item["used"] = 0

        return data
    return []

def save_data(data):
    json.dump(data, open(DATA_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

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
# JSON安全パース
# ===============================
def safe_json(text):
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
    return {}

# ===============================
# AI
# ===============================
def ai_extract(img):

    model_name = get_model()

    if not model_name:
        st.error("利用可能なモデルが見つかりません")
        return {}

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

    try:
        res = model.generate_content([prompt, img])
        return safe_json(res.text)
    except Exception as e:
        st.error(f"AIエラー: {e}")
        return {}

# ===============================
# UI
# ===============================
st.title("🎫 クーポン管理（リセット機能付き）")

# ===============================
# 🔴 全データリセット（追加）
# ===============================
st.sidebar.header("管理")

if st.sidebar.button("⚠️ 全データ初期化"):
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    st.success("全データを削除しました")
    st.rerun()

# ===============================
# アップロード
# ===============================
file = st.file_uploader("画像アップ", type=["jpg", "png", "jpeg"])

img = None

if file:
    img = Image.open(file)
    st.image(img)

    if st.button("AI解析"):
        st.session_state["ocr"] = ai_extract(img)

ocr = st.session_state.get("ocr", {})

# ===============================
# 入力
# ===============================
store = st.text_input("店舗名", value=ocr.get("store", ""))
discount = st.text_input("割引", value=ocr.get("discount", ""))

category = st.selectbox("カテゴリ", ["飲食", "物販", "サービス", "その他"])

quantity = st.number_input("枚数（総数）", 1, 100, 1)

expiry_default = datetime.today()
if ocr.get("expiry"):
    try:
        expiry_default = datetime.strptime(ocr["expiry"], "%Y-%m-%d")
    except:
        pass

expiry = st.date_input("期限", value=expiry_default)

# ===============================
# 保存
# ===============================
if st.button("保存"):

    data = load_data()

    data.append({
        "id": str(datetime.now().timestamp()),
        "store": store,
        "discount": discount,
        "category": category,
        "quantity": quantity,
        "used": 0,
        "expiry": str(expiry),
        "image": to_b64(img) if img else None
    })

    save_data(data)

    st.success("保存しました")
    st.rerun()

# ===============================
# 一覧
# ===============================
st.subheader("一覧")

data = load_data()
today = datetime.today().date()

for item in data:

    store = item.get("store", "不明")
    discount = item.get("discount", "")
    category = item.get("category", "")
    qty = item.get("quantity", 1)
    used = item.get("used", 0)
    exp = item.get("expiry", "")

    remaining = qty - used

    try:
        d = datetime.strptime(exp, "%Y-%m-%d").date()
        days = (d - today).days
    except:
        days = 999

    # 表示
    if days < 0:
        st.error(f"{store}（期限切れ）")
    elif days < 7:
        st.warning(f"{store}（あと{days}日 / 残り{remaining}枚）")
    else:
        st.success(f"{store}（{exp} / 残り{remaining}枚）")

    if item.get("image"):
        try:
            st.image(from_b64(item["image"]), width=200)
        except:
            pass

    st.write(f"""
カテゴリ: {category}  
割引: {discount}  
総数: {qty}  
使用済: {used}  
残り: {remaining}
""")

    # ===============================
    # 使用管理
    # ===============================
    col1, col2 = st.columns(2)

    with col1:
        if st.button("1枚使用", key=f"use_{item['id']}"):
            if item["used"] < item["quantity"]:
                item["used"] += 1
                save_data(data)
                st.rerun()

    with col2:
        if st.button("戻す", key=f"back_{item['id']}"):
            if item["used"] > 0:
                item["used"] -= 1
                save_data(data)
                st.rerun()

    # ===============================
    # 削除
    # ===============================
    if st.button("削除", key=f"del_{item['id']}"):
        data = [x for x in data if x["id"] != item["id"]]
        save_data(data)
        st.rerun()

    st.divider()
