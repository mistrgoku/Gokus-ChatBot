import os
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

# Načtení API klíče z prostředí na Renderu
api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key)

# Trik: Seznam modelů v pořadí od nejlepšího po záložní
MODELS_TO_TRY = [
    "llama-3.1-8b-instant",       # Hlavní rychlý model
    "llama3-70b-8192",            # První záložní model
    "mixtral-8x7b-32768"          # Druhý záložní model
]

@app.route("/")
def home():
    """Vykreslení hlavní stránky."""
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    """Spracování zpráv z chatu s automatickým záložním modelem."""
    data = request.get_json() or {}
    user_message = data.get("question", "") or data.get("message", "")
    user_message = user_message.strip()

    if not user_message:
        return jsonify({"answer": "Prosím, napiš nějakou zprávu.", "response": "Prosím, napiš nějakou zprávu."}), 400

    history_messages = data.get("history", [])
    messages = [{"role": "system", "content": "Jsi užitečný AI asistent."}]

    for msg in history_messages:
        messages.append({"role": msg.get("role"), "content": msg.get("content")})

    messages.append({"role": "user", "content": user_message})

    # Trik z praxe: Vyzkouší postupně modely ze seznamu
    for model_name in MODELS_TO_TRY:
        try:
            completion = client.chat.completions.create(
                messages=messages,
                model=model_name,
                temperature=0.7,
                max_tokens=1024,
            )
            bot_response = completion.choices[0].message.content
            # Vrací kompatibilní odpoveď pro klíče 'answer' i 'response'
            return jsonify({"answer": bot_response, "response": bot_response}), 200
        except Exception as e:
            print(f"Model {model_name} selhal: {e}. Zkouším další...")
            continue

    # Pokud selžou všechny modely v seznamu:
    return jsonify({"answer": "Omlouvám se, všechny AI modely jsou momentálně nedostupné.", "response": "Omlouvám se, všechny AI modely jsou momentálně nedostupné."}), 500

@app.route("/clear", methods=["POST"])
def clear():
    """Trasa pro vyčištění chatu."""
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
