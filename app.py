import os
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, session
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tajny-klic-goku-secure")

# Načtení API klíče z prostředí (Environment variables na Renderu)
api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# Jednoduché úložiště pro uživatele v paměti
users = {}

# Tvoje modely pro text
MODELS_TO_TRY = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

# Model pro zpracování obrázků (Vision)
VISION_MODEL = "llama-3.2-11b-vision-preview"

@app.route("/")
def home():
    if "user_email" not in session:
        return redirect(url_for("login"))
    display_name = session.get("display_name", "Goku")
    return render_template("index.html", display_name=display_name)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        if email in users and users[email]["password"] == password:
            session["user_email"] = email
            session["display_name"] = users[email]["display_name"]
            return redirect(url_for("home"))
        else:
            error = "Nesprávný e-mail nebo heslo."
            
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        if not display_name or not email or not password:
            error = "Vyplňte prosím všechna pole."
        elif email in users:
            error = "Tento e-mail je již zaregistrovaný."
        else:
            users[email] = {
                "display_name": display_name,
                "password": password
            }
            session["user_email"] = email
            session["display_name"] = display_name
            return redirect(url_for("home"))
            
    return render_template("register.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/ask", methods=["POST"])
def ask():
    if "user_email" not in session:
        return jsonify({"answer": "Nejste přihlášen.", "response": "Nejste přihlášen."}), 401

    if not client:
        return jsonify({
            "answer": "Chyba: GROQ_API_KEY není nastaven v prostředí (Environment).",
            "response": "Chyba: GROQ_API_KEY není nastaven v prostředí (Environment)."
        }), 500

    data = request.get_json() or {}
    user_message = data.get("question") or data.get("message") or data.get("text") or ""
    user_message = user_message.strip()
    image_base64 = data.get("image")  # Přečteme přiložený obrázek v Base64

    if not user_message and not image_base64:
        return jsonify({
            "answer": "Napiš prosím nějakou zprávu nebo přilož obrázek.",
            "response": "Napiš prosím nějakou zprávu nebo přilož obrázek."
        }), 400

    incoming_messages = data.get("messages", [])
    display_name = session.get("display_name", "Goku")
    user_email = session.get("user_email", "")

    # Systémové instrukce
    system_content = (
        f"Jsi Mistrův asistent, užitečný a přátelský AI asistent, kterým tě vytvořil člověk jménem Goku. "
        f"Uživatel, se kterým mluvíš, se jmenuje {display_name} a jeho e-mail je '{user_email}'. "
        f"Automaticky detekuj zemi, národní doménu e-mailu uživatele (.cz, .sk, .de, .fr apod.) "
        f"nebo jazyk jeho dotazu a ODPOVÍDEJ VŽDY V TOMTO DANÉM JAZYCE. "
        f"Máš kompletní znalost všech 100+ světových jazyků. "
        f"Pokud se tě kdokoliv zeptá, kdo tě vytvořil nebo naprogramoval, odpověz přesně touto větičkou: 'Vytvořil mě člověk jménem Goku.'"
    )
    
    messages = [{"role": "system", "content": system_content}]

    # Přidání historie konverzace (pouze textové zprávy pro historii)
    for msg in incoming_messages[:-1]:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Sestavení poslední uživatelské zprávy (podle toho, zda obsahuje obrázek)
    if image_base64:
        text_prompt = user_message if user_message else "Co je na tomto obrázku?"
        user_content = [
            {"type": "text", "text": text_prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": image_base64
                }
            }
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": user_message})

    # Určení modelů k vyzkoušení (pokud je přítomen obrázek, použije se Vision model)
    models_to_run = [VISION_MODEL] if image_base64 else MODELS_TO_TRY

    def generate():
        for model_name in models_to_run:
            try:
                completion = client.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    temperature=0.7,
                    max_tokens=1024,
                    stream=True
                )
                for chunk in completion:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield f"data: {json.dumps({'text': content})}\n\n"
                return
            except Exception as e:
                print(f"Model {model_name} selhal: {e}. Zkouším další...")
                continue

        yield f"data: {json.dumps({'text': 'Omlouvám se, všechny AI modely jsou momentálně nedostupné.'})}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")

@app.route("/clear", methods=["POST"])
def clear():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
