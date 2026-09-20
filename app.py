import os
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

# Načtení API klíče z prostředí (Environment variables na Renderu)
api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# Použití volně dostupných modelů z Groq API
MODELS_TO_TRY = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    if not client:
        return jsonify({
            "answer": "Chyba: GROQ_API_KEY není nastaven v prostředí (Environment).",
            "response": "Chyba: GROQ_API_KEY není nastaven v prostředí (Environment)."
        }), 500

    data = request.get_json() or {}
    user_message = data.get("question") or data.get("message") or data.get("text") or ""
    user_message = user_message.strip()

    if not user_message:
        return jsonify({
            "answer": "Napiš prosím nějakou zprávu.",
            "response": "Napiš prosím nějakou zprávu."
        }), 400

    history_messages = data.get("history", [])
    messages = [{"role": "system", "content": "Jsi užitečný a přátelský AI asistent."}]

    for msg in history_messages:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    # Vyzkoušíme postupně dostupné modely
    for model_name in MODELS_TO_TRY:
        try:
            completion = client.chat.completions.create(
                messages=messages,
                model=model_name,
                temperature=0.7,
                max_tokens=1024,
            )
            bot_response = completion.choices[0].message.content
            return jsonify({
                "answer": bot_response,
                "response": bot_response
            }), 200
        except Exception as e:
            print(f"Model {model_name} selhal: {e}. Zkouším další...")
            continue

    return jsonify({
        "answer": "Omlouvám se, všechny AI modely jsou momentálně nedostupné.",
        "response": "Omlouvám se, všechny AI modely jsou momentálně nedostupné."
    }), 500

@app.route("/clear", methods=["POST"])
def clear():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
