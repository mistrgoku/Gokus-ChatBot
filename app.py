import os
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

# Načtení API klíče z proměnných prostředí Renderu
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Inicializace klienta
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    if not client:
        return jsonify({"error": "GROQ_API_KEY není nastaven v Environment Variables!"}), 500

    data = request.json or {}
    user_question = data.get("question", "")
    history_messages = data.get("history", [])

    messages = [
        {"role": "system", "content": "Jsi užitečný a přátelský AI asistent."}
    ]

    for msg in history_messages:
        messages.append({"role": msg.get("role"), "content": msg.get("content")})

    if user_question:
        messages.append({"role": "user", "content": user_question})

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        answer = completion.choices[0].message.content
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Přidána ruta /clear, aby tlačítko pro smazání historie neházelo chybu 404
@app.route("/clear", methods=["POST"])
def clear():
    return jsonify({"status": "cleared"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
