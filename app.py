import os
import json
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tajny-klic-goku-secure")

# Databáze – vezme DATABASE_URL z Renderu, případně použije lokální SQLite
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    db_url = "sqlite:///database.db"
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Načtení Groq API klíče
groq_api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=groq_api_key) if groq_api_key else None

# Databázový model uživatele
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    display_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

# Vytvoření databázových tabulek
with app.app_context():
    db.create_all()

# Vybrané OpenAI modely běžící na Groq
MODELS_TO_TRY = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

VISION_MODEL = "llama-3.2-11b-vision-preview"

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", display_name=session.get("display_name", "Uživatel"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()

        user = User.query.filter_by(email=email).first()

        if user:
            # 1. Zkontroluje, zda heslo odpovídá šifrovanému tvaru (hash)
            # 2. Nebo zda odpovídá přesně v čistém textu (pro staré nešifrované účty)
            is_valid_hash = False
            try:
                is_valid_hash = check_password_hash(user.password_hash, password)
            except Exception:
                is_valid_hash = False

            if is_valid_hash or user.password_hash == password:
                # Pokud se přihlásil starým nešifrovaným heslem, rovnou ho zašifruje pro příště
                if not is_valid_hash:
                    user.password_hash = generate_password_hash(password)
                    db.session.commit()

                session["user_id"] = user.id
                session["user_email"] = user.email
                session["display_name"] = user.display_name

                if request.is_json:
                    return jsonify({"status": "success", "redirect": "/"})
                return redirect(url_for("home"))

        error_msg = "Nesprávný e-mail nebo heslo."
        if request.is_json:
            return jsonify({"status": "error", "message": error_msg}), 401
        return render_template("login.html", error=error_msg)

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        display_name = (data.get("display_name") or data.get("name") or "Uživatel").strip()
        email = (data.get("email") or "").strip().lower()
        password = (data.get("password") or "").strip()

        if not email or not password:
            error_msg = "Vyplňte e-mail a heslo."
            if request.is_json:
                return jsonify({"status": "error", "message": error_msg}), 400
            return render_template("register.html", error=error_msg)

        user = User.query.filter_by(email=email).first()

        # Pokud uživatel existuje, aktualizuje se mu heslo na správný hash
        if user:
            user.password_hash = generate_password_hash(password)
            user.display_name = display_name or user.display_name
            db.session.commit()
        else:
            hashed_password = generate_password_hash(password)
            user = User(display_name=display_name, email=email, password_hash=hashed_password)
            db.session.add(user)
            db.session.commit()

        session["user_id"] = user.id
        session["user_email"] = user.email
        session["display_name"] = user.display_name

        if request.is_json:
            return jsonify({"status": "success", "redirect": "/"})
        return redirect(url_for("home"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/ask", methods=["POST"])
def ask():
    if "user_id" not in session:
        return jsonify({"error": "Nejste přihlášen."}), 401

    if not client:
        return jsonify({"error": "Chyba: GROQ_API_KEY není nastaven v prostředí serveru."}), 500

    data = request.get_json() or {}
    user_message = (data.get("question") or data.get("message") or "").strip()
    image_base64 = data.get("image")
    incoming_messages = data.get("messages", [])

    display_name = session.get("display_name", "Uživatel")
    user_email = session.get("user_email", "")

    system_content = (
        f"Jsi Mistrův asistent, užitečný a přátelský AI asistent, kterého vytvořil Goku. "
        f"Uživatel se jmenuje {display_name} ({user_email}). "
        f"Odpovídej vždy plynule v jazyce, kterým na tebe uživatel mluví."
    )

    messages = [{"role": "system", "content": system_content}]

    for msg in incoming_messages[:-1]:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            if isinstance(msg["content"], str):
                messages.append({"role": msg["role"], "content": msg["content"]})

    if image_base64:
        image_formatted = image_base64 if image_base64.startswith("data:image/") else f"data:image/jpeg;base64,{image_base64}"
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_message or "Co je na tomto obrázku?"},
                {"type": "image_url", "image_url": {"url": image_formatted}}
            ]
        })
        models_to_run = [VISION_MODEL]
    else:
        messages.append({"role": "user", "content": user_message})
        models_to_run = MODELS_TO_TRY

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
                print(f"Model {model_name} selhal: {e}")
                continue

        yield f"data: {json.dumps({'text': 'Omlouvám se, model je momentálně nedostupný.'})}\n\n"

    return Response(stream_with_context(generate()), content_type="text/event-stream")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
