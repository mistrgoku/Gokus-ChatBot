import os
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

# Načtení API klíče z prostředí (Environment Variables)
api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    print("VAROVÁNÍ: GROQ_API_KEY není nastaven v proměnných prostředí!")

client = Groq(api_key=api_key)

@app.route("/")
def home():
    """Vykreslení hlavní stránky chatu."""
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    """Zpracování zpráv z chatu a volání AI modelu."""
    data = request.get_json()
    
    if not data:
        return jsonify({"response": "Chybná žádost, chybí data."}), 400

    user_message = data.get("message", "").strip()
    
    if not user_message:
        return jsonify({"response": "Prosím, napiš nějakou zprávu."}), 400

    try:
        # Použití dostupného modelu ze seznamu
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            model="openai/gpt-oss-120b",
            temperature=0.7,
            max_tokens=1024,
        )
        
        bot_response = completion.choices[0].message.content
        return jsonify({"response": bot_response}), 200

    except Exception as err:
        print(f"Chyba při komunikaci s API: {err}")
        return jsonify({"response": "Chyba při zpracování dotazu."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
