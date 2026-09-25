import os
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, session
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tajny-klic-goku-secure")

api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# Jednoduchá databáze v paměti (pro trvalé ukládání využijeme přidanou PostgreSQL)
users = {}

# Aktualizované a dostupné modely na Groqu
MODELS_TO_TRY = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

@app.route("/")
def home():
    if "user_email" not in session:
        return redirect(url_for("login"))
    display_name = session.get("display_name", "Uživatel")
    return render_template("index.html", display_name=display_name)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        # Kontrola v paměti (pokud uživatel existuje)
        if email in users and users[email]["password"] == password:
            session["user_email"] = email
            session["display_name"] = users[email]["display_name"]
            return redirect(url_for("home"))
        elif email not in users:
            error = "Účet s tímto e-mailem neexistuje. Nejprve se zaregistruj."
        else:
            error = "Nesprávné heslo."
            
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        if not display_name or not email or not password:
            error = "Vyplň prosím všechna pole."
        elif email in users:
            error = "Tento e-mail je již zaregistrovaný. Přihlas se."
        else:
            # Uložení nového účtu
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

    if not user_message:
        def empty_gen():
            yield f"data: {json.dumps({'text': 'Napsal jsi prázdnou zprávu. Zadej prosím text.'})}\n\n"
        return Response(stream_with_context(empty_gen()), content_type="text/event-stream")

    incoming_messages = data.get("messages", []) or data.get("history", [])
    display_name = session.get("display_name", "Uživatel")
    user_email = session.get("user_email", "")

    # Systémový prompt s předáním informací o přihlášeném uživateli
    system_content = (
        f"Jsi Mistrův asistent, užitečný a přátelský AI asistent, kterého vytvořil člověk jménem Goku. "
        f"Uživatel, se kterým mluvíš, se jmoveuje {display_name} a jeho e-mail je '{user_email}'. "
        f"Pokud se tě kdokoliv zeptá, kdo tě vytvořil nebo naprogramoval, odpověz přesně touto větou: 'Vytvořil mě člověk jménem Goku.'"
    )

    text_messages = [{"role": "system", "content": system_content}]
    for msg in incoming_messages:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            if isinstance(msg["content"], str) and msg["content"].strip():
                text_messages.append({"role": msg["role"], "content": msg["content"]})
    text_messages.append({"role": "user", "content": user_message})

    def generate():
        for model_name in MODELS_TO_TRY:
            try:
                completion = client.chat.completions.create(
                    messages=text_messages,
                    model=model_name,
                    temperature=0.7,
                    max_tokens=300,  # Snížený limit, aby nepadal na rate limit (OTPM)
                    stream=True
                )
                for chunk in completion:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield f"data: {json.dumps({'text': content})}\n\n"
                return
            except Exception as e:
                print(f"[GROQ ERROR] Model {model_name} selhal: {e}")
                continue

        yield f"data: {json.dumps({'text': 'Omlouvám se, všechny AI modely jsou momentálně nedostupné.'})}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")

@app.route("/clear", methods=["POST"])
def clear():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
