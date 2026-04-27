def ai_extract(img):
    import google.generativeai as genai

    # 安定化：候補モデル（上から順に試す）
    model_candidates = [
        "models/gemini-1.0-pro-vision",
        "models/gemini-pro-vision",
        "gemini-pro-vision",
        "models/gemini-1.0-pro"
    ]

    prompt = """
あなたはクーポン画像解析AIです。

画像から以下の情報を抽出し、必ずJSONのみで返してください。
説明文は禁止です。

{
  "store": "店舗名",
  "discount": "割引内容",
  "expiry": "YYYY-MM-DD",
  "note": "備考"
}

不明な項目は空文字にしてください。
"""

    last_error = None

    for model_name in model_candidates:
        try:
            model = genai.GenerativeModel(model_name)

            response = model.generate_content(
                contents=[prompt, img]
            )

            if response and response.text:
                return safe_json(response.text)

        except Exception as e:
            last_error = e
            continue

    # 全モデル失敗時
    import streamlit as st
    st.error(f"AI解析に失敗しました: {last_error}")
    return {}
