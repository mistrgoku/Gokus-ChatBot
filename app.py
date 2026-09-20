import os
import json
from flask import Flask, render_template, request, Response
from groq import Groq

app = Flask(__name__)

# Vložte váš API klíč přímo do uvozovek níže, např.: "gsk_..."
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or "ZDE_VLOZTE_VAS_GROQ_API_KLIC"

client = Groq(api_key=GROQ_API_KEY)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.json or {}
    user_question = data.get("question", "")
    history_messages = data.get("messages", [])

    messages = [
        {"role": "system", "content": "Jsi užitečný a přátelský asistent."}
    ]
    
    for msg in history_messages:
        messages.append({"role": msg.get("role"), "content": msg.get("content")})

    def generate():
        try:
            stream = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield json.dumps({"token": content}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return Response(generate(), mimetype="application/x-ndjson")

@app.route("/clear", methods=["POST"])
def clear():
    return json.dumps({"status": "success"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
