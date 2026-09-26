import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, session
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tajny-klic-goku-secure")

# Načtení API klíče z prostředí
api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key) if api_key else None

# Připojení k PostgreSQL databázi z prostředí Renderu
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Vytvoří tabulku 'users' v databázi, pokud ještě neexistuje."""
    if DATABASE_URL:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    display_name VARCHAR(100) NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password VARCHAR(200) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            cur.close()
            conn.close()
            print("[DATABASE] Tabulka 'users' byla úspěšně zkontrolována/inicializována.")
        except Exception as e:
            print(f"[DATABASE ERROR] Chyba při inicializaci databáze: {e}")

# Inicializace databáze při spuštění aplikace
init_db()

# Preferované pořadí modelů (od nejlepšího/nejchytřejšího po záložní)
PREFERRED_TEXT_MODELS = [
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b"
]

PREFERRED_VISION_MODELS = [
    "llama-3.2-11b-vision-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3.8-27b"
]

def get_best_models(is_vision=False):
    """
    Automaticky ověří dostupné modely přes Groq API 
    a vrátí seřazený seznam nejlepších dostupných modelů.
    """
    if not client:
        return []
    
    try:
        available_response = client.models.list()
        available_ids = [m.id for m in available_response.data]
    except Exception as e:
        print(f"[AUTO-ROUTER ERROR] Získání modelů selhalo: {e}")
        return PREFERRED_VISION_MODELS if is_vision else PREFERRED_TEXT_MODELS

    target_preferences = PREFERRED_VISION_MODELS if is_vision else PREFERRED_TEXT_MODELS
    active_models = [m_id for m_id in target_preferences if m_id in available_ids]
    
    if not active_models and available_ids:
        active_models = available_ids

    return active_models

# PŘIDÁNA PODPORA PRO "/" I "/home"
@app.route("/")
@app.route("/home")
def home():
    if "user_email" not in session:
        return redirect(url_for("login"))
    display_name = session.get("display_name", "Goku")
    return render_template("index.html", display_name=display_name)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
                user = cur.fetchone()
                cur.close()
                conn.close()

                if user:
                    session["user_email"] = user["email"]
                    session["display_name"] = user["display_name"]
                    return redirect(url_for("home"))
                else:
                    error = "Nesprávný e-mail nebo heslo."
            except Exception as e:
                error = f"Chyba při přihlašování: {e}"
        else:
            error = "Databáze není připojena (chybí DATABASE_URL)."
            
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        
        if not display_name or not email or not password:
            error = "Vyplňte prosím všechna pole."
        else:
            conn = get_db_connection()
            if conn:
                try:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO users (display_name, email, password) VALUES (%s, %s, %s)",
                        (display_name, email, password)
                    )
                    conn.commit()
                    cur.close()
                    conn.close()

                    session["user_email"] = email
                    session["display_name"] = display_name
                    return redirect(url_for("home"))
                except psycopg2.IntegrityError:
                    error = "Tento e-mail je již zaregistrovaný."
                except Exception as e:
                    error = f"Chyba databáze: {e}"
            else:
                error = "Databáze není připojena (chybí DATABASE_URL)."
            
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
        f"Uživatel, se kterým mluvíš, se jmoveje {display_name} a jeho e-mail je '{user_email}'. "
        f"Pokud se tě kdokoliv zeptá, kdo tě vytvořil nebo naprogramoval, odpověz přesně touto větičkou: 'Vytvořil mě člověk jnímim Goku.'"
    )

    def generate():
        # --- ROZHODOVÁNÍ: MÁME OBRÁZEK? ---
        if image_base64:
            vision_models = get_best_models(is_vision=True)
            
            if not image_base64.startswith("data:image/"):
                image_url_formatted = f"data:image/jpeg;base64,{image_base64}"
            else:
                image_url_formatted = image_base64

            prompt_text = user_message if user_message else "Co se nachází na tomto obrázku?"
            vision_payload = [{"role": "system", "content": system_content}]
            
            for msg in incoming_messages:
                if isinstance(msg, dict) and "role" in msg and "content" in msg:
                    if isinstance(msg["content"], str) and msg["content"].strip():
                        vision_payload.append({"role": msg["role"], "content": msg["content"]})

            vision_payload.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": image_url_formatted}}
                ]
            })

            for v_model in vision_models:
                try:
                    completion = client.chat.completions.create(
                        messages=vision_payload,
                        model=v_model,
                        temperature=0.7,
                        max_tokens=2048,
                        stream=True
                    )
                    for chunk in completion:
                        content = chunk.choices[0].delta.content or ""
                        if content:
                            yield f"data: {json.dumps({'text': content})}\n\n"
                    return
                except Exception as e:
                    print(f"[AUTO-ROUTER] Vision model {v_model} neuspěl: {e}. Zkouším další...")
                    continue

        # --- TEXT: POUŽIJEME NEJLEPŠÍ TEXTOVÝ MODEL ---
        text_models = get_best_models(is_vision=False)
        formatted_text_messages = [{"role": "system", "content": system_content}]
        
        for msg in incoming_messages:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                if isinstance(msg["content"], str) and msg["content"].strip():
                    formatted_text_messages.append({"role": msg["role"], "content": msg["content"]})

        formatted_text_messages.append({"role": "user", "content": user_message if user_message else "Ahoj!"})

        for t_model in text_models:
            try:
                completion = client.chat.completions.create(
                    messages=formatted_text_messages,
                    model=t_model,
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
                print(f"[AUTO-ROUTER] Text model {t_model} neuspěl: {e}")
                continue

        yield f"data: {json.dumps({'text': 'Omlouvám se, žádný AI model se nepodařilo kontaktovat.'})}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")

@app.route("/clear", methods=["POST"])
def clear():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
