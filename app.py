import os
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from groq import Groq

app = Flask(__name__)

# Načtení API klíče z prostředí (Environment variables na Renderu)
api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# Použití volně dostupných modelů z Groq API (ponechány přesně tvé modely)
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

    # Generátor pro postupné streamování odpovědi
    def generate():
        for model_name in MODELS_TO_TRY:
            try:
                completion = client.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    temperature=0.7,
                    max_tokens=1024,
                    stream=True  # Zapnutí streamování
                )
                for chunk in completion:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield f"data: {json.dumps({'text': content})}\n\n"
                return  # Úspěšně odesláno, ukončíme funkci
            except Exception as e:
                print(f"Model {model_name} selhal: {e}. Zkouším další...")
                continue

        # Pokud selžou všechny modely
        yield f"data: {json.dumps({'text': ' Omlouvám se, všechny AI modely jsou momentálně nedostupné.'})}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")

@app.route("/clear", methods=["POST"])
def clear():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
