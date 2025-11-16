from flask import Flask, request, jsonify, render_template_string
import json

app = Flask(__name__)

with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

SCHEMA_RULES = {
    "Başarısızlık": {
        "question_ids": [5, 23, 41, 59, 77],
        "threshold": 20,
        "description": "Başarısızlık şeması, bireyin kendisini yetersiz, başarısız ya da aptal hissetmesiyle karakterizedir."
    },
    "Terk Edilme": {
        "question_ids": [1, 19, 37, 55, 73],
        "threshold": 20,
        "description": "Terk edilme şeması, kişinin sevdiklerinin onu bırakacağına dair yoğun bir inanç taşımasıdır."
    }
}

@app.route("/")
def index():
    return render_template_string("""
        <!doctype html>
        <title>Kişilik Testi</title>
        <h1>Kişilik Testi</h1>
        <form method="post" action="/submit">
        {% for q in questions %}
          <p>{{ q["text"] }}</p>
          {% for opt in q["options"] %}
            <input type="radio" name="q{{ q['id'] }}" value="{{ opt['value'] }}" required> {{ opt['text'] }}<br>
          {% endfor %}
        {% endfor %}
        <input type="submit" value="Gönder">
        </form>
    """, questions=QUESTIONS)

@app.route("/submit", methods=["POST"])
def submit():
    responses = request.form
    scores = {}
    for k, v in responses.items():
        try:
            scores[int(k.strip("q"))] = int(v)
        except:
            continue

    triggered = []
    explanations = []
    for name, rule in SCHEMA_RULES.items():
        total = sum([scores.get(qid, 0) for qid in rule["question_ids"]])
        if total >= rule["threshold"]:
            triggered.append(name)
            explanations.append(f"<h3>{name}</h3><p>{rule['description']}</p>")

    html_result = "<h2>Test Sonucunuz</h2>"
    if triggered:
        html_result += "<h3>Tetiklenen Şemalar:</h3>" + "".join(explanations)
    else:
        html_result += "<p>Herhangi bir şema tetiklenmedi.</p>"
    html_result += '<p><a href="/">Yeniden Dene</a></p>'
    return html_result

if __name__ == "__main__":
    import os
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
