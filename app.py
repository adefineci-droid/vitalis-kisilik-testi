from flask import Flask, request, render_template_string, session, redirect, url_for
import json
import os 
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
# GİZLİ ANAHTAR: Oturum (Session) kullanmak için gereklidir.
app.secret_key = 'BU_COK_UZUN_VE_SABIT_BIR_GIZLI_ANAHTARDIR_1234567890ABCDEF' 

# Soruları yükle
try:
    with open("questions.json", "r", encoding="utf-8") as f:
        QUESTIONS = json.load(f)
    TOTAL_QUESTIONS = len(QUESTIONS)
except Exception as e:
    logging.error(f"HATA: questions.json yüklenemedi: {e}")
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

# --- GİRİŞ SAYFASI (INDEX) ---
@app.route("/")
def index():
    # Jinja2'nun CSS'i yanlış yorumlamasını engellemek için {% raw %} kullanıldı.
    landing_page_html = """
    <!doctype html>
    <title>Young Şema Testi - Giriş</title>
    <style>
        {% raw %}
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f7f6;
            margin: 0;
            padding: 20px;
            color: #333;
            text-align: center;
        }
        .container {
            max-width: 700px;
            margin: 0 auto;
            background-color: #fff;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            text-align: left;
        }
        h1 {
            color: #1e88e5;
            text-align: center;
            margin-bottom: 20px;
        }
        h3 {
            color: #555;
            border-bottom: 1px solid #eee;
            padding-bottom: 5px;
            margin-top: 25px;
        }
        p {
            line-height: 1.6;
            margin-bottom: 15px;
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            background-color: #e3f2fd;
            border-left: 5px solid #2196f3;
            padding: 10px 15px;
            margin-bottom: 10px;
            border-radius: 4px;
        }
        .start-button {
            display: inline-block;
            width: 100%;
            padding: 15px;
            background-color: #4CAF50; /* Yeşil Buton */
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-size: 1.2em;
            cursor: pointer;
            transition: background-color 0.3s;
            margin-top: 30px;
            text-align: center;
        }
        .start-button:hover {
            background-color: #388E3C;
        }
        {% endraw %}
    </style>

    <body>
        <div class="container">
            <h1>Young Şema Testine Hoş Geldiniz</h1>
            
            <h3>Test Hakkında Bilgilendirme</h3>
            <p>Bu test, toplam **3 aşamadan** oluşmaktadır ve Young Şema Terapisi modeli temel alınarak hazırlanmıştır. Şu anda cevaplayacağınız sorular, ilk aşamayı (Şema Değerlendirme) kapsamaktadır.</p>

            <h3>Testin Aşamaları</h3>
            <ul>
                <li>**1. Aşama (Şema Soruları):** Temel şemalarınızın şiddetini belirleyen soruları içerir.</li>
                <li>**2. Aşama (Tetikleyiciler):** Şemalarınızı hangi durumların tetiklediğine odaklanır.</li>
                <li>**3. Aşama (Başa Çıkma):** Şemalarınızla nasıl başa çıktığınızı değerlendirir.</li>
            </ul>

            <h3>Sonuçlar Nasıl Alınacak?</h3>
            <p>Tüm 3 aşamayı tamamladığınızda, sistem size hangi şemaların baskın olduğunu belirten kapsamlı bir sonuç raporu sunacaktır. Sonuçlar, her şemanın kısa bir açıklamasını ve yaşamınızdaki potansiyel etkilerini içerecektir.</p>
            
            <a href="{{ url_for('start_test') }}" class="start-button">Teste Başla</a>
        </div>
    </body>
    """
    return render_template_string(landing_page_html)

# --- YENİ BAŞLANGIÇ ROTASI (SESSION İLKLEME) ---
@app.route("/start_test")
def start_test():
    if not QUESTIONS:
        return "HATA: Sorular yüklenemedi. Lütfen 'questions.json' dosyanızı kontrol edin.", 500
        
    # Oturumu temizle ve yeni bir teste hazırla
    session.clear()
    session['current_question_index'] = 0
    session['answers'] = {}
    return redirect(url_for('quiz'))

# --- QUIZ ROTASI ---
@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    # Session başlatma /start_test rotasına taşındığı için burada kontrol etmeye gerek yok.
    current_index = session.get('current_question_index', 0)
    
    # Session'ın başlangıçta ayarlanıp ayarlanmadığını kontrol et
    if 'answers' not in session:
        return redirect(url_for('start_test'))
    
    if request.method == "POST":
        question_id_str = request.form.get('question_id')
        
        if question_id_str:
            answer_value_str = request.form.get(f'q{question_id_str}')
            
            answer_processed_successfully = False 
            
            try:
                if answer_value_str is None:
                    # Cevap seçilmeden post edilirse, sayfayı yeniden yükle
                    return redirect(url_for('quiz'))

                answer_value = int(answer_value_str)
                session['answers'][question_id_str] = answer_value
                answer_processed_successfully = True
                
            except (ValueError, TypeError) as e:
                logging.warning(f"Cevap işlenirken kritik hata: {e}. Soru ID: {question_id_str}, Cevap Değeri: {answer_value_str}")
                
            if answer_processed_successfully:
                session['current_question_index'] += 1
                current_index = session['current_question_index']
                
            return redirect(url_for('quiz'))


    # --- GET İsteği İşleme (Soru Gösterimi) ---
    
    if current_index >= TOTAL_QUESTIONS:
        return redirect(url_for('submit'))
        
    if not QUESTIONS:
        return "HATA: Sorular yüklenemedi.", 500

    try:
        q = QUESTIONS[current_index]
    except IndexError:
        return redirect(url_for('submit'))
        
    # İlerleme çubuğu için yüzdelik hesaplama
    progress_percent = round(((current_index + 1) / TOTAL_QUESTIONS) * 100)
        
    # {% raw %} ile CSS hatası çözüldü
    question_html = """
    <!doctype html>
    <title>Young Şema Testi ({{ current_index_display }}/{{ total_questions }})</title>
    <style>
        {% raw %}
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f7f6;
            margin: 0;
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 700px;
            margin: 0 auto;
            background-color: #fff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
        }
        h1 {
            color: #1e88e5;
            text-align: center;
            margin-bottom: 5px;
        }
        h2 {
            font-size: 1.2em;
            color: #555;
            text-align: center;
            margin-bottom: 25px;
        }
        /* İlerleme Çubuğu Stilleri */
        #progress-bar-container {
            height: 8px;
            background-color: #e0e0e0;
            border-radius: 4px;
            margin-bottom: 25px;
            overflow: hidden;
        }
        #progress-bar {
            height: 100%;
            background-color: #4CAF50;
            transition: width 0.4s ease;
        }
        .card {
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            background-color: #fcfcfc;
        }
        .question-text {
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #333;
        }
        .options-list {
            display: grid;
            gap: 10px;
            margin-top: 15px;
        }
        /* Radyo butonunu gizle */
        input[type="radio"] {
            display: none;
        }
        /* Seçenek kartı görünümü */
        .option-card {
            display: block;
            padding: 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 1em;
            font-weight: 500;
        }
        .option-card:hover {
            border-color: #b3d9ff;
            background-color: #e6f2ff;
        }
        /* Seçili kartın görünümü */
        input[type="radio"]:checked + .option-card {
            border-color: #1e88e5;
            background-color: #e0f7fa;
            color: #1e88e5;
            box-shadow: 0 0 5px rgba(30, 136, 229, 0.5);
        }
        input[type="submit"] {
            width: 100%;
            padding: 12px;
            background-color: #1e88e5; /* Mavi Buton */
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1.1em;
            cursor: pointer;
            transition: background-color 0.3s;
            margin-top: 20px;
        }
        input[type="submit"]:hover {
            background-color: #1565c0;
        }
        {% endraw %}
    </style>

    <body>
        <div class="container">
            <h1>Young Şema Testi</h1>
            <h2>Soru {{ current_index_display }} / {{ total_questions }}</h2>
            
            <div id="progress-bar-container">
                <div id="progress-bar" style="width: {{ progress_percent }}%;"></div>
            </div>
            
            <form method="post" action="{{ url_for('quiz') }}">
                <input type="hidden" name="question_id" value="{{ question.id }}">
                
                <div class="card">
                    <p class="question-text"><strong>{{ question.text }}</strong></p> 
                    
                    <div class="options-list">
                        {% for opt in options %}
                            <label>
                                <input type="radio" name="q{{ question.id }}" value="{{ opt.value }}" required>
                                <span class="option-card">{{ opt.text }}</span>
                            </label>
                        {% endfor %}
                    </div>
                </div>
                
                <input type="submit" value="Sonraki Soru">
            </form>
        </div>
    </body>
    """
    
    return render_template_string(
        question_html, 
        current_index_display=current_index + 1,
        total_questions=TOTAL_QUESTIONS,
        progress_percent=progress_percent,
        question=q,
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
        total = sum([scores.get(str(qid), 0) for qid in rule["question_ids"]])
        if total >= rule["threshold"]:
            triggered.append(name)
            explanations.append(f"<h3>{name}</h3><p>{rule['description']}</p>")

    # {% raw %} ile CSS hatası çözüldü
    result_template = """
    <!doctype html>
    <title>Young Şema Testi - Sonuç</title>
    <style>
        {% raw %}
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; color: #333; text-align: center; }
        .container { max-width: 600px; margin: 0 auto; background-color: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08); text-align: left; }
        h2 { color: #1e88e5; text-align: center; margin-bottom: 20px; }
        h3 { color: #e53935; border-bottom: 2px solid #ffcdd2; padding-bottom: 5px; margin-top: 20px; }
        p { line-height: 1.6; }
        a { display: inline-block; margin-top: 20px; padding: 10px 20px; background-color: #1e88e5; color: white; text-decoration: none; border-radius: 8px; transition: background-color 0.3s; }
        a:hover { background-color: #1565c0; }
        {% endraw %}
    </style>
    <body>
        <div class="container">
            <h2>Young Şema Testi Sonuçları</h2>
            {{ result_content | safe }}
            <p style="text-align: center;"><a href="/">Yeniden Başla</a></p>
        </div>
    </body>
    """
    
    # Dinamik içerik oluşturuluyor
    result_content = ""
    if triggered:
        result_content += "<h3>Tetiklenen Şemalar:</h3>" + "".join(explanations)
    else:
        result_content += "<p>Tebrikler! Belirgin olarak tetiklenmiş bir şema tespit edilmedi.</p>"
    
    result_content += f'<p>Toplam Cevaplanan Soru: {len(scores)}/{TOTAL_QUESTIONS}</p>'
    
    
    # template'i render_template_string ile işliyoruz
    return render_template_string(
        result_template,
        result_content=result_content
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
