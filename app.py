import os
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

@app.route('/')
def index():
    return render_template('index.html')

# TADY JSME ZMĚNILI /chat NA /ask, ABY TO ODPOVÍDALO TVÉMU FRONTONDU
@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.json
        # Načteme zprávu (podporuje klíče "message" i "prompt")
        user_message = data.get("message") or data.get("prompt") or ""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        bot_reply = response.choices[0].message.content
        return jsonify({"response": bot_reply, "answer": bot_reply})

    except Exception as e:
        return jsonify({"error": f"TEST CHYBA: {str(e)}"}), 500

# PŘIDÁNO /clear, ABY TLAČÍTKO NA VYČIŠTĚNÍ CHATU NEHÁZELO CHYBU 404
@app.route('/clear', methods=['POST'])
def clear():
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
