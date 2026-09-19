import os
from flask import Flask, render_template_string, request, jsonify
from groq import Groq

app = Flask(__name__)

# Načtení API klíče z Render prostředí
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gokus AI ChatBot</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Roboto, sans-serif; }
        body { background-color: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .chat-container { width: 100%; max-width: 600px; height: 85vh; background: #1e293b; border-radius: 16px; display: flex; flex-direction: column; box-shadow: 0 10px 25px rgba(0,0,0,0.5); overflow: hidden; border: 1px solid #334155; }
        .chat-header { background: #1e293b; padding: 18px 20px; text-align: center; font-size: 1.25rem; font-weight: bold; border-bottom: 1px solid #334155; color: #38bdf8; }
        .chat-messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
        .message { max-width: 80%; padding: 12px 16px; border-radius: 12px; font-size: 0.95rem; line-height: 1.5; word-wrap: break-word; }
        .user-message { background: #2563eb; color: white; align-self: flex-end; border-bottom-right-radius: 2px; }
        .bot-message { background: #334155; color: #f1f5f9; align-self: flex-start; border-bottom-left-radius: 2px; }
        .chat-input { display: flex; padding: 16px; background: #0f172a; gap: 10px; border-top: 1px solid #334155; }
        input { flex: 1; padding: 12px 16px; border: 1px solid #334155; border-radius: 8px; background: #1e293b; color: white; outline: none; font-size: 0.95rem; }
        input:focus { border-color: #38bdf8; }
        button { padding: 12px 24px; background: #2563eb; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 0.95rem; transition: background 0.2s; }
        button:hover { background: #1d4ed8; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">Gokus AI ChatBot</div>
        <div class="chat-messages" id="messages">
            <div class="message bot-message">Ahoj! Jsem tvoji AI asistent. Jak ti mohu dnes pomoci?</div>
        </div>
        <div class="chat-input">
            <input type="text" id="userInput" placeholder="Napiš zprávu..." onkeypress="if(event.key==='Enter') sendMessage()">
            <button onclick="sendMessage()">Odeslat</button>
        </div>
    </div>

    <script>
        async function sendMessage() {
            const input = document.getElementById('userInput');
            const message = input.value.trim();
            if (!message) return;

            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML += `<div class="message user-message">${message}</div>`;
            input.value = '';
            messagesDiv.scrollTop = messagesDiv.scrollHeight;

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: message })
                });
                const data = await response.json();
                const reply = data.response || data.error || 'Chyba serveru';
                
                messagesDiv.innerHTML += `<div class="message bot-message">${reply}</div>`;
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } catch (e) {
                messagesDiv.innerHTML += `<div class="message bot-message">Chyba při připojení k serveru.</div>`;
            }
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    user_message = data.get("message", "")

    if not client:
        return jsonify({"error": "GROQ_API_KEY není nastaven v Environment Variables."}), 500

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        bot_response = completion.choices[0].message.content
        return jsonify({"response": bot_response})
    except Exception as e:
        return jsonify({"error": f"Chyba při komunikaci s AI: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
