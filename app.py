import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super-tajny-klic-123")

def get_db_connection():
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        return conn
    except Exception as e:
        print(f"Chyba připojení k databázi: {e}")
        return None

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            error = "Zadej prosím e-mail a heslo."
            return render_template("login.html", error=error)

        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                
                # 1. Zjistíme, zda uživatel s tímto e-mailem už existuje
                cur.execute("SELECT * FROM users WHERE LOWER(email) = %s", (email,))
                user = cur.fetchone()

                if user:
                    # ÚČET EXISTUJE -> Ověříme heslo (podporuje i stará nezahešovaná hesla)
                    stored_pw = user["password"]
                    is_valid = False
                    
                    if stored_pw.startswith("pbkdf2:") or stored_pw.startswith("scrypt:"):
                        is_valid = check_password_hash(stored_pw, password)
                    else:
                        is_valid = (stored_pw == password)

                    if is_valid:
                        session["user_email"] = user["email"]
                        session["display_name"] = user["display_name"]
                        cur.close()
                        conn.close()
                        return redirect(url_for("home"))
                    else:
                        error = "Nesprávné heslo."
                else:
                    # ÚČET NEEXISTUJE -> Automaticky ho vytvoříme (Registrace)
                    name_to_save = display_name if display_name else email.split("@")[0]
                    hashed_pw = generate_password_hash(password)

                    cur.execute(
                        "INSERT INTO users (display_name, email, password) VALUES (%s, %s, %s) RETURNING *",
                        (name_to_save, email, hashed_pw)
                    )
                    new_user = cur.fetchone()
                    conn.commit()

                    session["user_email"] = new_user["email"]
                    session["display_name"] = new_user["display_name"]

                    cur.close()
                    conn.close()
                    return redirect(url_for("home"))

                cur.close()
                conn.close()
            except Exception as e:
                error = f"Chyba databáze: {e}"
        else:
            error = "Chyba připojení k databázi."

    return render_template("login.html", error=error)

@app.route("/home")
def home():
    if "user_email" not in session:
        return redirect(url_for("login"))
    return f"Vítej v chatu, {session.get('display_name')}!"

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
