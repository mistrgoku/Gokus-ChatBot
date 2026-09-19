import os
from flask import Flask, render_template_string, request, jsonify
from groq import Groq

app = Flask(__name__)

# Načtení API klíče z prostředí (Environment Variables na Renderu)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cortex Chat</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { display: flex; flex-direction: column; height: 100vh; background-color: #f0f2f5; }
        header { background-color: #3b82f6; color: white; padding: 15px 20px; font-size: 20px; font-weight: bold; }
        #chat-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 10px; }
        .message { max-width: 70%; padding: 12px 16px; border-radius: 18px; line-height: 1.4; word-wrap: break-word; }
        .user { align-self: flex-end; background-color: #3b82f6; color: white; border-bottom-right-radius: 4px; }
        .bot { align-self: flex-start; background-color: white; color: #333; border-bottom-left-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
        .error { align-self: center; background-color: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; max-width: 90%; }
        #input-container { display: flex; padding: 15px; background: white; border-top: 1px solid #ddd; }
        #user-input { flex: 1; padding: 12px; border: 1px solid #ccc; border-radius: 20px; outline: none; font-size: 16px; }
        #send-btn { margin-left: 10px; padding: 12px 24px; background-color: #3b82f6; color: white; border: none; border-radius: 20px; cursor: pointer; font-weight: bold; }
        #send-btn:hover { background-color: #2563eb; }
    </style>
</head>
<body>
    <header>ahoj</header>
    <div id="chat-container"></div>
    <div id="input-container">
        <input type="text" id="user-input" placeholder="Napište zprávu..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button id="send-btn" onclick="sendMessage()">Odeslat</button>
    </div>

    <script>
        async function sendMessage() {
            const input = document.getElementById('user-input');
            const text = input.value.trim();
            if (!text) return;

            appendMessage(text, 'user');
            input.value = '';

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await response.json();
                if (data.error) {
                    appendMessage(data.error, 'error');
                } else {
                    appendMessage(data.response, 'bot');
                }
            } catch (err) {
                appendMessage('Chyba při komunikaci se serverem.', 'error');
            }
        }

        function appendMessage(text, side) {
            const container = document.getElementById('chat-container');
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${side}`;
            msgDiv.innerText = text;
            container.appendChild(msgDiv);
            container.scrollTop = container.scrollHeight;
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
    data = request.get_json()
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
        return jsonify({"error": f"Error code: {e}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
