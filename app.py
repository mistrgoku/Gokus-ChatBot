import os
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, session
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tajny-klic-goku-secure")

# Načtení API klíče z prostředí
api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# Úložiště pro uživatele v paměti
users = {}

def get_groq_models(need_vision=False):
    """Dynamicky načte aktuálně podporované modely z API."""
    if not client:
        return []
    try:
        models_page = client.models.list()
        all_models = [m.id for m in models_page.data]
        
        valid_models = [
            m for m in all_models 
            if "whisper" not in m and "safeguard" not in m and "guard" not in m
        ]

        if need_vision:
            vision_models = [m for m in valid_models if "vision" in m]
            return vision_models if vision_models else ["llama-3.2-11b-vision-instruct"]
        else:
            text_models = [m for m in valid_models if "vision" not in m]
            return text_models if text_models else ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    except Exception as e:
        print(f"[GROQ ERROR] Načítání modelů selhalo: {e}")
        return ["llama-3.2-11b-vision-instruct"] if need_vision else ["llama-3.3-70b-versatile"]

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
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "").strip()
        
        if not display_name or not password:
            error = "Vyplňte prosím jméno i heslo."
        else:
            # Pokud uživatel existuje, zkontrolujeme heslo
            if display_name in users:
                if users[display_name]["password"] == password:
                    session["user_email"] = display_name
                    session["display_name"] = display_name
                    return redirect(url_for("home"))
                else:
                    error = "Uživatel s tímto jménem již existuje, ale zadal jsi špatné heslo."
            else:
                # Pokud neexistuje, automaticky ho zaregistrujeme
                users[display_name] = {
                    "password": password,
                    "display_name": display_name
                }
                session["user_email"] = display_name
                session["display_name"] = display_name
                return redirect(url_for("home"))
            
    return render_template("login.html", error=error)

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
    image_base64 = data.get("image") or data.get("image_base64")

    if not user_message and not image_base64:
        def empty_gen():
            yield f"data: {json.dumps({'text': 'Napsal jsi prázdnou zprávu.'})}\n\n"
        return Response(stream_with_context(empty_gen()), content_type="text/event-stream")

    incoming_messages = data.get("messages", []) or data.get("history", [])
    display_name = session.get("display_name", "Goku")
    user_email = session.get("user_email", "")

    system_content = (
        f"Jsi Mistrův asistent, užitečný a přátelský AI asistent, kterého vytvořil člověk jménem Goku. "
        f"Uživatel, se kterým mluvíš, se jmenuje {display_name} a jeho e-mail/nick je '{user_email}'. "
        f"Dokážeš analyzovat text i obrázky. "
        f"Pokud se tě kdokoliv zeptá, kdo tě vytvořil nebo naprogramoval, odpověz přesně touto větičkou: 'Vytvořil mě člověk jménem Goku.'"
    )

    formatted_messages = [{"role": "system", "content": system_content}]

    for msg in incoming_messages:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            if isinstance(msg["content"], str) and msg["content"].strip():
                formatted_messages.append({"role": msg["role"], "content": msg["content"]})

    if image_base64:
        models_to_try = get_groq_models(need_vision=True)
        
        if not image_base64.startswith("data:image/"):
            image_url_formatted = f"data:image/jpeg;base64,{image_base64}"
        else:
            image_url_formatted = image_base64

        prompt_text = user_message if user_message else "Co se nachází na tomto obrázku?"
        user_content = [
            {"type": "text", "text": prompt_text},
            {
                "type": "image_url",
                "image_url": {"url": image_url_formatted}
            }
        ]
        formatted_messages.append({"role": "user", "content": user_content})
    else:
        models_to_try = get_groq_models(need_vision=False)
        if not formatted_messages or formatted_messages[-1].get("content") != user_message:
            formatted_messages.append({"role": "user", "content": user_message})

    def generate():
        last_error = ""
        for model_name in models_to_try:
            try:
                completion = client.chat.completions.create(
                    messages=formatted_messages,
                    model=model_name,
                    temperature=0.7,
                    max_tokens=500,
                    stream=True
                )
                for chunk in completion:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield f"data: {json.dumps({'text': content})}\n\n"
                return
            except Exception as e:
                last_error = str(e)
                print(f"[GROQ ERROR] Model {model_name} selhal: {e}")
                continue

        yield f"data: {json.dumps({'text': f'Chyba při zpracování: {last_error}'})}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")

@app.route("/clear", methods=["POST"])
def clear():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
