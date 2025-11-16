from flask import Flask, request, render_template_string, session, redirect, url_for
import json
import os 
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
# SABİT GİZLİ ANAHTAR
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
            
            answer_processed_successfully = False 
            
            try:
                if answer_value_str is None:
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
        
    # question_html'i Python f-string'i olarak tutmaya devam ediyoruz, ancak Jinja2 
    # ifadelerini dörtlü süslü parantez ile koruyoruz ve Python değişkenlerini doğrudan CSS'e basıyoruz.
    question_html = f"""
    <!doctype html>
    <title>Young Şema Testi ({{{{ current_index_display }}}}/{{{{ total_questions }}}})</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f7f6;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        .container {{
            max-width: 700px;
            margin: 0 auto;
            background-color: #fff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
        }}
        h1 {{
            color: #1e88e5;
            text-align: center;
            margin-bottom: 5px;
        }}
        h2 {{
            font-size: 1.2em;
            color: #555;
            text-align: center;
            margin-bottom: 25px;
        }}
        /* İlerleme Çubuğu Stilleri */
        #progress-bar-container {{
            height: 8px;
            background-color: #e0e0e0;
            border-radius: 4px;
            margin-bottom: 25px;
            overflow: hidden;
        }}
        #progress-bar {{
            height: 100%;
            width: {progress_percent}%; /* Python'dan gelen değişken */
            background-color: #4CAF50; /* Yeşil ilerleme çubuğu */
            transition: width 0.4s ease;
        }}
        .card {{
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            background-color: #fcfcfc;
        }}
        .question-text {{
            font-size: 1.2em;
            margin-bottom: 15px;
            color: #333;
        }}
        .options-list {{
            display: grid;
            gap: 10px;
            margin-top: 15px;
        }}
        /* Radyo butonunu gizle */
        input[type="radio"] {{
            display: none;
        }}
        /* Seçenek kartı görünümü */
        .option-card {{
            display: block;
            padding: 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 1em;
            font-weight: 500;
        }}
        .option-card:hover {{
            border-color: #b3d9ff;
            background-color: #e6f2ff;
        }}
        /* Seçili kartın görünümü */
        input[type="radio"]:checked + .option-card {{
            border-color: #1e88e5;
            background-color: #e0f7fa;
            color: #1e88e5;
            box-shadow: 0 0 5px rgba(30, 136, 229, 0.5);
        }}
        input[type="submit"] {{
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
        }}
        input[type="submit"]:hover {{
            background-color: #1565c0;
        }}
    </style>

    <body>
        <div class="container">
            <h1>Young Şema Testi</h1>
            <h2>Soru {{{{ current_index_display }}}} / {{{{ total_questions }}}}</h2>
            
            <div id="progress-bar-container">
                <div id="progress
