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

# Seznam nejnovějších, oficiálně podporovaných textových modelů na Groq API
MODELS_TO_TRY = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768"
]

# Pokusný Vision model (pokud by ho Groq zrovna podporoval)
VISION_MODELS = [
    "llama-3.2-11b-vision-instruct",
    "llama-3.2-90b-vision-instruct"
]

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
        return jsonify({"answer": "Nejste přihlášen."}), 401

    if not client:
        def no_key_gen():
            yield f"data: {json.dumps({'text': 'Chyba: GROQ_API_KEY není nastaven v Environment Variables.'})}\n\n"
        return Response(stream_with_context(no_key_gen()), content_type="text/event-stream")

    data = request.get_json() or {}
    user_message = (data.get("question") or data.get("message") or data.get("text") or "").strip()
    image_base64 = data.get("image")

    if not user_message and not image_base64:
        def empty_gen():
            yield f"data: {json.dumps({'text': 'Napsal jsi prázdnou zprávu. Zadej prosím text.'})}\n\n"
        return Response(stream_with_context(empty_gen()), content_type="text/event-stream")

    incoming_messages = data.get("messages", []) or data.get("history", [])
    display_name = session.get("display_name", "Goku")
    user_email = session.get("user_email", "")

    system_content = (
        f"Jsi Mistrův asistent, užitečný a přátelský AI asistent, kterého vytvořil člověk jménem Goku. "
        f"Uživatel, se kterým mluvíš, se jmenuje {display_name} a jeho e-mail je '{user_email}'. "
        f"Pokud se tě kdokoliv zeptá, kdo tě vytvořil nebo naprogramoval, odpověz přesně touto větou: 'Vytvořil mě člověk jménem Goku.'"
    )
    
    # Sestavení zpráv pro textové modely
    text_messages = [{"role": "system", "content": system_content}]
    for msg in incoming_messages:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            if isinstance(msg["content"], str) and msg["content"].strip():
                text_messages.append({"role": msg["role"], "content": msg["content"]})
    text_messages.append({"role": "user", "content": user_message if user_message else "Ahoj!"})

    # Sestavení zpráv pro vision modely (pokud je přítomen obrázek)
    vision_messages = None
    if image_base64:
        image_url_formatted = image_base64 if image_base64.startswith("data:image/") else f"data:image/jpeg;base64,{image_base64}"
        text_prompt = user_message if user_message else "Co je na tomto obrázku?"
        
        vision_messages = [{"role": "system", "content": system_content}]
        for msg in incoming_messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                if isinstance(msg["content"], str) and msg["content"].strip():
                    vision_messages.append({"role": msg["role"], "content": msg["content"]})
        
        user_content = [
            {"type": "text", "text": text_prompt},
            {"type": "image_url", "image_url": {"url": image_url_formatted}}
        ]
        vision_messages.append({"role": "user", "content": user_content})

    def generate():
        # 1. Pokud je přítomen obrázek, nejprve zkusíme Vision modely
        if vision_messages:
            for v_model in VISION_MODELS:
                try:
                    completion = client.chat.completions.create(
                        messages=vision_messages,
                        model=v_model,
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
                    print(f"[GROQ VISION ERROR] Model {v_model} selhal: {e}. Přecházím na textové modely...")
                    continue

        # 2. Běžné textové dotazy (nebo záložní plán, pokud vision selže)
        for t_model in MODELS_TO_TRY:
            try:
                completion = client.chat.completions.create(
                    messages=text_messages,
                    model=t_model,
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
                print(f"[GROQ TEXT ERROR] Model {t_model} selhal: {e}")
                continue

        yield f"data: {json.dumps({'text': 'Omlouvám se, všechny AI modely jsou momentálně nedostupné.'})}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")

@app.route("/clear", methods=["POST"])
def clear():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
