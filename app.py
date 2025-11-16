from flask import Flask, request, render_template_string, session, redirect, url_for
import json
import os 
import logging # Hata ayıklama için logging ekliyoruz

# Flask'ın hata loglarını görebilmek için temel yapılandırma
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# SABİT GİZLİ ANAHTAR: Session sorununu çözmeli.
app.secret_key = 'BU_COK_UZUN_VE_SABIT_BIR_GIZLI_ANAHTARDIR_1234567890ABCDEF' 

# Soruları yükle (Dosya okuma hatası olabilir, bunu da loglayalım)
try:
    with open("questions.json", "r", encoding="utf-8") as f:
        QUESTIONS = json.load(f)
    TOTAL_QUESTIONS = len(QUESTIONS)
except FileNotFoundError:
    logging.error("HATA: questions.json dosyası bulunamadı.")
    QUESTIONS = []
    TOTAL_QUESTIONS = 0
except json.JSONDecodeError:
    logging.error("HATA: questions.json dosyası geçersiz JSON formatında.")
    QUESTIONS = []
    TOTAL_QUESTIONS = 0


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
    if not QUESTIONS:
        return "HATA: Sorular yüklenemedi. Lütfen 'questions.json' dosyanızı kontrol edin.", 500
        
    session.clear()
    session['current_question_index'] = 0
    session['answers'] = {}
    return redirect(url_for('quiz'))

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    current_index = session.get('current_question_index', 0)
    
    if request.method == "POST":
        question_id_str = request.form.get('question_id')
        
        if question_id_str:
            answer_value_str = request.form.get(f'q{question_id_str}')
            
            try:
                # Cevap ID'sini ve değerini güvenli bir şekilde integer'a çevir
                question_id = int(question_id_str)
                answer_value = int(answer_value_str)
                
                session['answers'][question_id] = answer_value
                session['current_question_index'] += 1
                current_index = session['current_question_index']
                
            except (ValueError, TypeError) as e:
                # Eğer çevrim hatası olursa, bu muhtemelen 500 hatasına neden oluyordu.
                logging.warning(f"Cevap işlenirken hata: {e}. Soru ID: {question_id_str}, Cevap Değeri: {answer_value_str}")
                # Hata olsa bile kullanıcıyı bir sonraki soruya yönlendir (cevap kaydedilmeden)
                session['current_question_index'] += 1
                current_index = session['current_question_index']
                
    
    if current_index >= TOTAL_QUESTIONS:
        return redirect(url_for('submit'))
        
    # Güvenlik kontrolü: Eğer sorular yüklenemediyse buraya gelmemeli, ama yine de kontrol edelim.
    if not QUESTIONS:
        return "HATA: Sorular yüklenemedi.", 500

    try:
        q = QUESTIONS[current_index]
    except IndexError as e:
        # Index hatası, yani soru listesi beklenenden kısa. Sonuca yönlendir.
        logging.error(f"Index hatası: {e}. Mevcut Index: {current_index}, Toplam Soru: {TOTAL_QUESTIONS}")
        return redirect(url_for('submit'))
        
    # Soru için HTML şablonu oluştur
    question_html = """
    <!doctype html>
    <title>Kişilik Testi ({{ current_index_display }}/{{ total_questions }})</title>
    <h1>Kişilik Testi</h1>
    <h2>Soru {{ current_index_display }} / {{ total_questions }}</h2>
    
    <form method="post" action="{{ url_for_quiz }}">
        <input type="hidden" name="question_id" value="{{ question_id }}">
        
        <p><strong>{{ question_text }}</strong></p> 
        
        {% for opt in options %}
        <input type="radio" name="q{{ question_id }}" value="{{ opt['value'] }}" required> {{ opt['text'] }}<br>
        {% endfor %}
        
        <br>
        <input type="submit" value="Sonraki Soru">
    </form>
    """
    
    # Şablonu render et ve dinamik değişkenleri aktar
    return render_template_string(
        question_html, 
        current_index_display=current_index + 1,
        total_questions=TOTAL_QUESTIONS,
        url_for_quiz=url_for('quiz'),
        question_id=q['id'],
        question_text=q['text'],
        options=q["options"]
    )


@app.route("/submit")
def submit():
    scores = session.get('answers', {})
    
    if not scores:
        return redirect(url_for('index'))
    
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
    html_result += f'<p>Toplam Cevaplanan Soru: {len(scores)}/{TOTAL_QUESTIONS}</p>'
    html_result += '<p><a href="/">Yeniden Başla</a></p>'
    
    session.clear() 
    return html_result


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
