import streamlit as st
import json
import os
from datetime import datetime
import re
from PIL import Image
import google.generativeai as genai

# ===============================
# UI設定
# ===============================
st.set_page_config(
    page_title="クーポン管理",
    layout="centered"
)

st.title("🎟 クーポン管理アプリ（画像サムネイル対応）")

# ===============================
# 保存先
# ===============================
DATA_FILE = "coupons.json"
IMG_DIR = "images"

os.makedirs(IMG_DIR, exist_ok=True)

# ===============================
# API初期化
# ===============================
GEMINI_OK = False

try:
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if api_key:
        genai.configure(api_key=api_key)
        GEMINI_OK = True
except:
    pass

# ===============================
# データ読み込み（互換対応）
# ===============================
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 旧データ救済
            for d in data:
                if "store" not in d:
                    d["store"] = d.get("name", "不明")

                if "image" not in d:
                    d["image"] = ""

                if "expiry" not in d:
                    d["expiry"] = "2100-01-01"

                if "quantity" not in d:
                    d["quantity"] = 1

            return data
        except:
            return []
    return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===============================
# モデル取得
# ===============================
def get_model():
    try:
        models = genai.list_models()
        for m in models:
            if "generateContent" in m.supported_generation_methods:
                return m.name
    except:
        pass
    return "models/gemini-1.5-pro-001"

# ===============================
# 画像保存（サムネイル化）
# ===============================
def save_image(image, store_name):
    safe = re.sub(r"[^0-9a-zA-Zぁ-んァ-ン一-龥]", "_", store_name or "coupon")
    filename = f"{safe}_{datetime.now().timestamp()}.jpg"
    path = os.path.join(IMG_DIR, filename)

    img = image.copy()
    img.thumbnail((300, 300))
    img.save(path, "JPEG", quality=70)

    return path

# ===============================
# AI解析
# ===============================
def ai(image):
    if not GEMINI_OK:
        return None

    model = genai.GenerativeModel(get_model())

    prompt = """
クーポン画像から以下を抽出してください：

store（店舗名）
discount（割引内容）
expiry（YYYY-MM-DD）

JSONのみで返してください。
"""

    try:
        res = model.generate_content([prompt, image])
        raw = res.text

        cleaned = re.sub(r"```json|```", "", raw).strip()

        return json.loads(cleaned)
    except:
        return None

# ===============================
# 画像アップロード
# ===============================
file = st.file_uploader("📸 クーポン画像")

if file:
    image = Image.open(file)
    st.image(image, use_container_width=True)

    if st.button("⚡ AI解析"):
        with st.spinner("解析中..."):
            result = ai(image)

        if result:
            st.session_state["draft"] = result
            st.session_state["image"] = image
            st.success("解析成功")
        else:
            st.error("解析失敗")

st.divider()

# ===============================
# 入力フォーム
# ===============================
draft = st.session_state.get("draft", {})
image = st.session_state.get("image", None)

store = st.text_input("店舗名", draft.get("store", ""))
discount = st.text_input("割引", draft.get("discount", ""))
category = st.selectbox("カテゴリ", ["飲食", "物販", "サービス", "その他"])

expiry = st.date_input("有効期限")
qty = st.number_input("枚数", 1, 100, 1)

# ===============================
# 保存
# ===============================
if st.button("💾 保存"):

    image_path = ""

    if image is not None:
        image_path = save_image(image, store)

    data = load_data()

    data.append({
        "store": store,
        "category": category,
        "discount": discount,
        "quantity": qty,
        "expiry": str(expiry),
        "image": image_path,
        "history": []
    })

    save_data(data)

    st.session_state["draft"] = {}
    st.session_state["image"] = None

    st.success("保存しました")
    st.rerun()

st.divider()

# ===============================
# 一覧（サムネイル表示）
# ===============================
st.subheader("📋 クーポン一覧")

data = load_data()
today = datetime.today().date()

for i, item in enumerate(data):

    store_name = item.get("store", "不明")

    try:
        exp = datetime.strptime(item.get("expiry", "2100-01-01"), "%Y-%m-%d").date()
        days = (exp - today).days
    except:
        days = 999

    col1, col2 = st.columns([1, 3])

    with col1:
        if item.get("image") and os.path.exists(item["image"]):
            st.image(item["image"], width=80)
        else:
            st.write("📄")

    with col2:
        if days < 0:
            st.error(f"⚠ {store_name}")
        elif days < 7:
            st.warning(f"⏳ {store_name}（{days}日）")
        else:
            st.success(store_name)

        st.write(f"""
💰 {item.get('discount','')}
🔢 {item.get('quantity',1)}
""")

    if st.button("🗑 削除", key=f"d{i}"):
        data.pop(i)
        save_data(data)
        st.rerun()

    st.markdown("---")