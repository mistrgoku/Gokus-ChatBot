import os
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    try:
        # Získat seznam všech dostupných modelů přímo z Groq API
        models_page = client.models.list()
        available_models = [m.id for m in models_page.data]
        
        # Vrátíme seznam modelů do chatu jako test
        return jsonify({
            "response": f"TEST ÚSPĚŠNÝ! Tvůj API klíč má přístup k těmto modelům: {', '.join(available_models)}"
        })

    except Exception as e:
        return jsonify({"error": f"TEST CHYBA PŘI NAČÍTÁNÍ MODELŮ: {str(e)}"}), 500

@app.route('/clear', methods=['POST'])
def clear():
    return jsonify({"status": "cleared"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
