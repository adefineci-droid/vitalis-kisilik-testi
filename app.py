from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import json

app = Flask(__name__)
# Oturumları kullanmak için bir gizli anahtar ayarlayın.
# Bunu güvenli bir şekilde gizli tutmanız ve bir ortam değişkeninden almanız önerilir.
app.secret_key = 'super_secret_key_veya_daha_iyisi_bir_ortam_degiskeni' 

# Soruları yükle
with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)
    
TOTAL_QUESTIONS = len(QUESTIONS)

SCHEMA_RULES = {
    "Başarısızlık": {
        "question_ids": [5, 23, 41, 59, 77],
        "threshold": 20,
        "description": "Başarısızlık şeması, bireyin kendisini yetersiz, başarısız ya da aptal hissetmesiyle karakterizedir.",
    },
    "Terk Edilme": {
        "question_ids": [1, 19, 37, 55, 73],
        "threshold": 20,
        "description": "Terk edilme şeması, kişinin sevdiklerinin onu bırakacağına dair yoğun bir inanç taşımasıdır.",
    }
}

@app.route("/")
def index():
    # Yeni bir test başladığında veya ana sayfaya dönüldüğünde oturumu sıfırla
    session.clear()
    session['current_question_index'] = 0
    session['answers'] = {}
    return redirect(url_for('quiz'))

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    current_index = session.get('current_question_index', 0)
    
    if request.method == "POST":
        # Önceki sorunun cevabını kaydet
        question_id = request.form.get('question_id')
        answer_value = request.form.get(f'q{question_id}')
        
        if question_id and answer_value:
            session['answers'][int(question_id)] = int(answer_value)
            session['current_question_index'] += 1
            current_index = session['current_question_index']
            
    # Tüm sorular bitti mi kontrol et
    if current_index >= TOTAL_QUESTIONS:
        return redirect(url_for('submit')) # Sonuç sayfasına yönlendir
        
    # Mevcut soruyu göster
    q = QUESTIONS[current_index]
    
    # Soru için HTML şablonu oluştur
    question_html = f"""
    <!doctype html>
    <title>Kişilik Testi ({current_index + 1}/{TOTAL_QUESTIONS})</title>
    <h1>Kişilik Testi</h1>
    <h2>Soru {current_index + 1} / {TOTAL_QUESTIONS}</h2>
    
    <form method="post" action="{url_for('quiz')}">
        <input type="hidden" name="question_id" value="{q['id']}">
        
        <p><strong>{q['text']}</strong></p> 
        
        {% for opt in options %}
        <input type="radio" name="q{q['id']}" value="{{ opt['value'] }}" required> {{ opt['text'] }}<br>
        {% endfor %}
        
        <br>
        <input type="submit" value="Sonraki Soru">
    </form>
    """
    
    return render_template_string(question_html, options=q["options"])


@app.route("/submit")
def submit():
    scores = session.get('answers', {})
    
    if not scores:
        return redirect(url_for('index')) # Cevap yoksa ana sayfaya dön
    
    triggered = []
    explanations = []
    
    # Şema sonuçlarını hesapla
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
    html_result += f'<p>Toplam Cevaplanan Soru: {len(scores)}/{TOTAL_QUESTIONS}</p>'
    html_result += '<p><a href="/">Yeniden Başla</a></p>'
    
    # Test sonuçlandıktan sonra oturumu temizle
    session.clear() 
    return html_result


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
