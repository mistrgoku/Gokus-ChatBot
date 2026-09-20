import os
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

# Načtení API klíče z prostředí
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get("message", "")

        # Volání aktuálně funkčního modelu Groq
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        bot_reply = response.choices[0].message.content
        return jsonify({"response": bot_reply})

    except Exception as e:
        # TEST CHYBA pro ověření, že Render načítá nový kód z GitHubu
        return jsonify({"error": f"TEST CHYBA: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
