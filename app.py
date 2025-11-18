from flask import Flask, request, render_template_string, session, redirect, url_for
import json
import os 
import logging
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import redis
from flask_session import Session

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = 'BU_COK_UZUN_VE_SABIT_BIR_GIZLI_ANAHTARDIR_1234567890ABCDEF' 

# --- VERİTABANI AYARLARI ---
db_uri = os.environ.get('DATABASE_URL')
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- OTURUM AYARLARI (Redis) ---
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
try:
    redis_url = os.environ.get('REDIS_URL')
    if not redis_url:
        logging.error("UYARI: REDIS_URL bulunamadı.")
    else:
        app.config['SESSION_REDIS'] = redis.from_url(redis_url)
        server_session = Session(app)
except Exception as e:
    logging.error(f"Redis Hatası: {e}")

# --- SORULARI YÜKLE ---
QUESTIONS_DATA = {}
try:
    with open("questions.json", "r", encoding="utf-8") as f:
        QUESTIONS_DATA = json.load(f)
except Exception as e:
    logging.error(f"questions.json yüklenemedi: {e}")

# --- KURALLAR ---

# 1. Aşama: Şemalar
SCHEMA_RULES_STAGE_1 = {
    "Duygusal Yoksunluk": { "question_ids": [1, 19, 37, 55, 73], "threshold": 20, "description": "Kişinin normal düzeyde duygusal destek alamayacağına dair inancıdır (örneğin; ilgi, şefkat, koruma)." },
    "Terk Edilme": { "question_ids": [2, 20, 38, 56, 74], "threshold": 20, "description": "Terk edilme şeması, kişinin sevdiklerinin onu bırakacağına dair yoğun bir inanç taşımasıdır." },
    "Kuşkuculuk": { "question_ids": [3, 21, 39, 57, 75, 44], "threshold": 24, "description": "Başkalarının niyetlerinden şüphe duyma ve güvenmeme eğilimidir." },
    "Sosyal İzolasyon": { "question_ids": [4, 40, 58, 76], "threshold": 16, "description": "Kişinin kendisini dünyanın geri kalanından soyutlanmış, farklı veya bir gruba ait değilmiş gibi hissetmesidir." },
    "Kusurluluk": { "question_ids": [5, 23, 41, 59, 77, 43, 90], "threshold": 28, "description": "Kişinin kendisini kusurlu, kötü, istenmeyen veya aşağılık hissetmesidir." },
    "Başarısızlık": { "question_ids": [6, 24, 42, 60, 78], "threshold": 20, "description": "Başarısızlık şeması, bireyin kendisini yetersiz, başarısız ya da aptal hissetmesiyle karakterizedir." },
    "Bağımlılık": { "question_ids": [7, 25, 61, 79], "threshold": 16, "description": "Başkalarının yardımı olmadan günlük sorumlulukları yerine getirememe inancıdır." },
    "Dayanıksızlık": { "question_ids": [8, 26, 80, 17, 35, 53, 89], "threshold": 28, "description": "Her an bir felaketin (tıbbi, mali, doğal) başına gelebileceği korkusudur." },
    "İç İçelik": { "question_ids": [9, 27, 45, 63, 81], "threshold": 20, "description": "Ebeveynlerle veya partnerle aşırı duygusal yakınlık ve bireyselleşememe durumudur." },
    "Boyun Eğicilik": { "question_ids": [10, 28, 46, 64, 82], "threshold": 20, "description": "Başkalarının kontrolü altında hissetme ve kendi isteklerini bastırma eğilimidir." },
    "Kendini Feda": { "question_ids": [11, 29, 47, 65, 83], "threshold": 20, "description": "Başkalarının ihtiyaçlarını kendi ihtiyaçlarının önüne koyma eğilimidir." },
    "Duyguları Bastırma": { "question_ids": [12, 30, 48, 66, 84], "threshold": 20, "description": "Duyguların ve dürtülerin aşırı kontrol edilmesi ve bastırılmasıdır." },
    "Statü Arayıcılık": { "question_ids": [13, 31, 14, 16, 34, 52, 70, 88], "threshold": 32, "description": "Başkalarının onayı, takdiri ve statü kazanma odaklı yaşama halidir." },
    "Yetersiz Özdenetim": { "question_ids": [15, 33, 51, 69, 87], "threshold": 20, "description": "Kişisel hedeflere ulaşmak için gereken disiplini sağlayamama durumudur." },
    "Büyüklenmecilik": { "question_ids": [22, 32, 50, 68, 86], "threshold": 20, "description": "Kişinin kendisini diğerlerinden üstün görmesi ve ayrıcalıklı hissetmesidir." },
    "Cezalandırıcılık": { "question_ids": [49, 67, 85, 18, 36, 59, 72], "threshold": 28, "description": "Hata yapanların sert bir şekilde cezalandırılması gerektiğine dair inançtır." },
    "Ekonomik Dayanıksızlık": { "question_ids": [62, 71], "threshold": 8, "description": "Maddi güvencesizlik ve parasal konularda aşırı endişe duyma halidir." }
}

# 2. Aşama: Başa Çıkma
COPING_RULES_STAGE_2 = {
    "Aşırı Telafi": { "question_ids": [1, 5, 8, 10], "threshold": 16, "description": "Aşırı telafi biçiminde kişi, şemanın öne sürdüğü olumsuz inançların tam tersini göstermeye çalışarak şemayla savaşır. “Yetersizim” şemasına karşı mükemmeliyetçilik, “değersizim” şemasına karşı kontrolcü veya üstün davranışlar gelişebilir." },
    "Teslim": { "question_ids": [2, 6, 9, 11], "threshold": 16, "description": "Bu biçimde kişi, sahip olduğu olumsuz inançların doğru olduğuna inanır ve bu inançlara uygun davranır. “Ben değersizim”, “Kimse beni sevmez” gibi düşünceler davranışlarını yönlendirebilir." },
    "Kaçınma": { "question_ids": [3, 4, 7, 12], "threshold": 16, "description": "Kaçınma biçiminde kişi, olumsuz duyguları veya hatırlatıcı durumları yaşamamak için duygusal, bilişsel ya da davranışsal olarak uzak durur." }
}

# --- VERİTABANI MODELİ ---
class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Demografik
    cinsiyet = db.Column(db.String(50))
    yas_araligi = db.Column(db.String(50))
    medeni_durum = db.Column(db.String(50))
    birlikte_yasam = db.Column(db.String(50))
    iliski_tanimi = db.Column(db.String(100))
    iliski_suresi = db.Column(db.String(50))
    terapi_destegi = db.Column(db.String(50))
    
    # Sonuçlar
    triggered_stage1 = db.Column(db.Text)
    triggered_stage2 = db.Column(db.Text)
    triggered_stage3 = db.Column(db.Text)
    
    # Ham veri
    all_answers_json = db.Column(db.Text)

with app.app_context():
    db.create_all()

# --- ROTALAR ---

@app.route("/")
def index():
    # (Mevcut Demografik Form HTML Kodunuz Buraya Gelecek - Değişmedi)
    landing_page_html = """
    <!doctype html>
    <title>Young Şema Testi - Giriş</title>
    <style>
        {% raw %}
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; color: #333; text-align: center; }
        .container { max-width: 700px; margin: 0 auto; background-color: #fff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1); text-align: left; }
        h1 { color: #1e88e5; text-align: center; margin-bottom: 20px; }
        h3 { color: #555; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 25px; }
        p { line-height: 1.6; margin-bottom: 15px; }
        .form-group { margin-bottom: 20px; padding: 15px; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #f9f9f9; }
        .form-group label { font-weight: 600; display: block; margin-bottom: 10px; color: #333; }
        .form-options { display: flex; flex-wrap: wrap; gap: 10px; }
        .form-options label { font-weight: 400; display: flex; align-items: center; background-color: #fff; border: 1px solid #ccc; border-radius: 5px; padding: 8px 12px; cursor: pointer; transition: background-color 0.2s, border-color 0.2s; }
        .form-options input[type="radio"] { margin-right: 8px; accent-color: #1e88e5; }
        .form-options label:hover { background-color: #eef8ff; }
        .form-options input[type="radio"]:checked + span { font-weight: 600; }
        .start-button { display: inline-block; width: 100%; padding: 15px; background-color: #4CAF50; color: white; text-decoration: none; border: none; border-radius: 8px; font-size: 1.2em; cursor: pointer; transition: background-color 0.3s; margin-top: 30px; text-align: center; }
        .start-button:hover { background-color: #388E3C; }
        {% endraw %}
    </style>
    <body>
        <div class="container">
            <h1>Young Şema Testine Hoş Geldiniz</h1>
            <h3>Test Hakkında Bilgilendirme</h3>
            <p>Bu test, toplam **3 aşamadan** oluşmaktadır ve Young Şema Terapisi modeli temel alınarak hazırlanmıştır.</p>
            <p>Lütfen aşağıdaki demografik bilgi formunu doldurarak teste başlayın.</p>

            <form action="{{ url_for('start_test') }}" method="POST">
                <div class="form-group">
                    <label>Cinsiyetiniz nedir?</label>
                    <div class="form-options">
                        <label><input type="radio" name="cinsiyet" value="Kadin" required> <span>Kadın</span></label>
                        <label><input type="radio" name="cinsiyet" value="Erkek"> <span>Erkek</span></label>
                    </div>
                </div>
                <div class="form-group">
                    <label>Yaş Aralığınız</label>
                    <div class="form-options">
                        <label><input type="radio" name="yas_araligi" value="18-24" required> <span>18–24</span></label>
                        <label><input type="radio" name="yas_araligi" value="25-31"> <span>25–31</span></label>
                        <label><input type="radio" name="yas_araligi" value="32-39"> <span>32–39</span></label>
                        <label><input type="radio" name="yas_araligi" value="40+"> <span>40 ve üzeri</span></label>
                    </div>
                </div>
                <div class="form-group">
                    <label>Medeni Durumunuz</label>
                    <div class="form-options">
                        <label><input type="radio" name="medeni_durum" value="Sevgili" required> <span>Sevgili</span></label>
                        <label><input type="radio" name="medeni_durum" value="Nisanli"> <span>Nişanlı</span></label>
                        <label><input type="radio" name="medeni_durum" value="Evli"> <span>Evli</span></label>
                    </div>
                </div>
                <div class="form-group">
                    <label>Partnerinizle birlikte yaşıyor musunuz?</label>
                    <div class="form-options">
                        <label><input type="radio" name="birlikte_yasam" value="Evet" required> <span>Evet</span></label>
                        <label><input type="radio" name="birlikte_yasam" value="Hayir"> <span>Hayır</span></label>
                    </div>
                </div>
                <div class="form-group">
                    <label>Partnerinizle ilişkinizi nasıl tanımlarsınız?</label>
                    <div class="form-options">
                        <label><input type="radio" name="iliski_tanimi" value="Sevgi Bagi" required> <span>Sevgi Bağı</span></label>
                        <label><input type="radio" name="iliski_tanimi" value="Aliskanlik"> <span>Alışkanlık</span></label>
                        <label><input type="radio" name="iliski_tanimi" value="Mecburiyet"> <span>Mecburiyet</span></label>
                    </div>
                </div>
                <div class="form-group">
                    <label>Şu anki ilişkinizin süresi ne kadardır?</label>
                    <div class="form-options">
                        <label><input type="radio" name="iliski_suresi" value="0-6 Ay" required> <span>0–6 ay</span></label>
                        <label><input type="radio" name="iliski_suresi" value="6-12 Ay"> <span>6–12 ay</span></label>
                        <label><input type="radio" name="iliski_suresi" value="1-3 Yil"> <span>1–3 yıl</span></label>
                        <label><input type="radio" name="iliski_suresi" value="3+ Yil"> <span>3 yıldan uzun</span></label>
                    </div>
                </div>
                <div class="form-group">
                    <label>Daha önce bir terapistten psikolojik destek aldınız mı?</label>
                    <div class="form-options">
                        <label><input type="radio" name="terapi_destegi" value="Aldim" required> <span>Aldım</span></label>
                        <label><input type="radio" name="terapi_destegi" value="Aliyorum"> <span>Alıyorum</span></label>
                        <label><input type="radio" name="terapi_destegi" value="Hayir"> <span>Hayır, almadım</span></label>
                    </div>
                </div>

                <button type="submit" class="start-button">Teste Başla</button>
            </form>
        </div>
    </body>
    """
    return render_template_string(landing_page_html)

@app.route("/start_test", methods=["GET", "POST"])
def start_test():
    session.clear()
    if request.method == "POST":
        session['demographics'] = request.form.to_dict()
    
    session['current_stage'] = 1
    session['current_question_index'] = 0
    session['answers_stage1'] = {}
    session['answers_stage2'] = {}
    session['answers_stage3'] = {}
    
    return redirect(url_for('quiz'))

@app.route("/start_stage_2")
def start_stage_2():
    session['current_stage'] = 2
    session['current_question_index'] = 0
    return redirect(url_for('quiz'))

@app.route("/start_stage_3")
def start_stage_3():
    session['current_stage'] = 3
    session['current_question_index'] = 0
    return redirect(url_for('quiz'))

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    stage = session.get('current_stage', 1)
    index = session.get('current_question_index', 0)
    
    stage_key = f"stage{stage}"
    current_questions = QUESTIONS_DATA.get(stage_key, [])
    total_questions = len(current_questions)
    
    stage_titles = {
        1: "Bölüm 1: Young Şema Testi",
        2: "Bölüm 2: Şema Başa Çıkma Biçimleri",
        3: "Bölüm 3: Yenilenmiş Çift Uyum Ölçeği"
    }
    current_title = stage_titles.get(stage, f"Bölüm {stage}")

    if request.method == "POST":
        qid = request.form.get('question_id')
        ans = request.form.get(f'q{qid}')
        
        if ans:
            session[f'answers_stage{stage}'][qid] = int(ans)
            session.modified = True
            session['current_question_index'] += 1
            return redirect(url_for('quiz'))

    if index >= total_questions:
        if stage == 1:
            return render_template_string("""
                <div style="text-align:center; padding:50px; font-family:sans-serif;">
                    <h1 style="color:#1e88e5;">1. Bölüm Tamamlandı</h1>
                    <p>Şimdi şema başa çıkma biçimlerinizi belirlemek için 2. bölüme geçiyoruz.</p>
                    <a href="/start_stage_2" style="background:#4CAF50; color:white; padding:15px 30px; text-decoration:none; border-radius:5px; font-size:1.2em;">2. Bölüme Başla</a>
                </div>
            """)
        elif stage == 2:
            return render_template_string("""
                <div style="text-align:center; padding:50px; font-family:sans-serif;">
                    <h1 style="color:#1e88e5;">2. Bölüm Tamamlandı</h1>
                    <p>Şimdi son bölüm olan Çift Uyum Ölçeği'ne geçiyoruz.</p>
                    <a href="/start_stage_3" style="background:#4CAF50; color:white; padding:15px 30px; text-decoration:none; border-radius:5px; font-size:1.2em;">3. Bölüme Başla</a>
                </div>
            """)
        else:
            return redirect(url_for('submit'))

    if not current_questions:
        return f"HATA: {stage}. aşama soruları bulunamadı.", 500

    question = current_questions[index]
    progress_percent = round(((index + 1) / total_questions) * 100)
    
    question_html = """
    <!doctype html>
    <title>{{ title }} - Soru {{ index_display }}/{{ total }}</title>
    <style>
        {% raw %}
        body { font-family: sans-serif; background: #f4f7f6; padding: 20px; color: #333; }
        .container { max-width: 700px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        h1 { color: #1e88e5; text-align: center; }
        .option-card { display: block; padding: 15px; border: 2px solid #ddd; border-radius: 8px; margin-top: 10px; cursor: pointer; }
        .option-card:hover { background: #e6f2ff; border-color: #b3d9ff; }
        input[type="radio"]:checked + .option-card { background: #e0f7fa; border-color: #1e88e5; color: #1e88e5; }
        input[type="radio"] { display: none; }
        input[type="submit"] { width: 100%; padding: 15px; background: #1e88e5; color: white; border: none; border-radius: 8px; margin-top: 20px; cursor: pointer; font-size: 1.1em;}
        {% endraw %}
    </style>
    <body>
        <div class="container">
            <h1>{{ title }}</h1>
            <p>Soru {{ index_display }} / {{ total }}</p>
            <div style="background:#e0e0e0; height:8px; border-radius:4px; margin-bottom:20px;">
                <div style="height:100%; background:#4CAF50; width:{{ progress }}%;"></div>
            </div>
            
            <form method="post">
                <input type="hidden" name="question_id" value="{{ q.id }}">
                <p style="font-size:1.2em; font-weight:bold;">{{ q.text }}</p>
                
                {% for opt in q.options %}
                <label>
                    <input type="radio" name="q{{ q.id }}" value="{{ opt.value }}" required>
                    <span class="option-card">{{ opt.text }}</span>
                </label>
                {% endfor %}
                
                <input type="submit" value="Sonraki Soru">
            </form>
        </div>
    </body>
    """
    
    return render_template_string(question_html, q=question, title=current_title, index_display=index+1, total=total_questions, progress=progress_percent)


@app.route("/submit")
def submit():
    s1 = session.get('answers_stage1', {})
    s2 = session.get('answers_stage2', {})
    s3 = session.get('answers_stage3', {})
    
    # Görünüm için HTML listeleri (Akordiyonlu)
    html_s1, html_s2, html_s3 = [], [], []
    # Veritabanı için İsim listeleri
    db_s1, db_s2, db_s3 = [], [], []

    # --- 1. AŞAMA ---
    for name, rule in SCHEMA_RULES_STAGE_1.items():
        total = sum([s1.get(str(qid), 0) for qid in rule["question_ids"]])
        if total >= rule["threshold"]:
            db_s1.append(name)
            # HTML için Akordiyon
            html_s1.append(f"""
            <div class="schema-card">
                <details>
                    <summary>{name}</summary>
                    <div class="details-content">
                        <p>{rule['description']}</p>
                    </div>
                </details>
            </div>
            """)

    # --- 2. AŞAMA ---
    for name, rule in COPING_RULES_STAGE_2.items():
        total = sum([s2.get(str(qid), 0) for qid in rule["question_ids"]])
        if total >= rule["threshold"]:
            db_s2.append(name)
            html_s2.append(f"""
            <div class="schema-card">
                <details>
                    <summary>{name}</summary>
                    <div class="details-content">
                        <p>{rule['description']}</p>
                    </div>
                </details>
            </div>
            """)

    # --- 3. AŞAMA (ÇİFT UYUMU) ---
    total_score_3 = 0
    for qid in range(1, 15):
        raw_score = s3.get(str(qid), 0)
        if raw_score == 0: continue
        if 7 <= qid <= 14: # Ters Puanlama (7-14 arası)
            score = 6 - raw_score
        else:
            score = raw_score
        total_score_3 += score
    
    uyum_sonuc = ""
    uyum_detay = ""
    if total_score_3 >= 35:
        uyum_sonuc = "İlişki Çift Uyumunuz: %50'nin Üzerindedir"
        uyum_detay = "Bu durum, ilişkide orta-yüksek düzeyde uyum olduğunu göstermektedir."
    else:
        uyum_sonuc = "İlişki Çift Uyumunuz: %50'nin Altındadır"
        uyum_detay = "Bu durum, ilişkide bazı uyum farklarının olabileceğini göstermektedir."
    
    # 3. Aşama sonuçlarını ekle
    db_s3.append(uyum_sonuc)
    html_s3.append(f"""
    <div class="schema-card">
        <div style="padding:15px; font-weight:bold; color:#333;">
            {uyum_sonuc} <br>
            <span style="font-weight:normal; font-size:0.9em; color:#666;">{uyum_detay}</span>
        </div>
    </div>
    """)

    # --- VERİTABANINA KAYIT ---
    try:
        demog = session.get('demographics', {})
        new_result = TestResult(
            cinsiyet=demog.get('cinsiyet'),
            yas_araligi=demog.get('yas_araligi'),
            medeni_durum=demog.get('medeni_durum'),
            birlikte_yasam=demog.get('birlikte_yasam'),
            iliski_tanimi=demog.get('iliski_tanimi'),
            iliski_suresi=demog.get('iliski_suresi'),
            terapi_destegi=demog.get('terapi_destegi'),
            # Temiz isimleri kaydet
            triggered_stage1=" | ".join(db_s1), 
            triggered_stage2=" | ".join(db_s2),
            triggered_stage3=" | ".join(db_s3),
            all_answers_json=json.dumps({"s1":s1, "s2":s2, "s3":s3})
        )
        db.session.add(new_result)
        db.session.commit()
    except Exception as e:
        logging.error(f"Kayıt Hatası: {e}")

    # --- SONUÇ SAYFASI (CSS Geri Geldi) ---
    result_template = """
    <!doctype html>
    <title>Sonuçlar</title>
    <style>
        {% raw %}
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; color: #333; text-align: center; }
        .container { max-width: 700px; margin: 0 auto; background-color: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08); text-align: left; }
        h2 { color: #1e88e5; text-align: center; margin-bottom: 20px; }
        h3 { color: #333; border-bottom: 1px solid #ccc; padding-bottom: 5px; margin-top: 30px; font-size: 1.3em; }
        
        /* AKORDİYON STİLLERİ */
        .schema-card { border: 1px solid #ddd; border-radius: 8px; margin-bottom: 15px; background-color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.05); transition: box-shadow 0.2s; }
        .schema-card:hover { box-shadow: 0 4px 8px rgba(0,0,0,0.08); }
        details { font-family: inherit; }
        summary { padding: 16px 20px; cursor: pointer; font-size: 1.1em; font-weight: 600; color: #e53935; list-style: none; display: flex; justify-content: space-between; align-items: center; }
        summary::-webkit-details-marker { display: none; }
        summary::after { content: '+'; font-size: 1.5em; font-weight: 300; color: #1e88e5; transition: transform 0.2s; }
        details[open] summary { border-bottom: 1px solid #eee; }
        details[open] summary::after { content: '−'; }
        .details-content { padding: 16px 20px; border-top: 1px solid #eee; line-height: 1.6; color: #333; }
        .empty-msg { color: #888; font-style: italic; padding: 10px; }
        {% endraw %}
    </style>
    <body>
        <div class="container">
            <h2>Test Sonuçlarınız</h2>
            
            <h3>1. Bölüm: Şemalar</h3>
            {% if res1 %}
                {% for r in res1 %}{{ r|safe }}{% endfor %}
            {% else %}<p class="empty-msg">Belirgin bir şema bulunamadı.</p>{% endif %}
            
            <h3>2. Bölüm: Başa Çıkma Biçimleri</h3>
            {% if res2 %}
                {% for r in res2 %}{{ r|safe }}{% endfor %}
            {% else %}<p class="empty-msg">Belirgin bir başa çıkma biçimi bulunamadı.</p>{% endif %}
            
            <h3>3. Bölüm: Çift Uyumu</h3>
             {% if res3 %}
                {% for r in res3 %}{{ r|safe }}{% endfor %}
            {% else %}<p class="empty-msg">Sonuç hesaplanamadı.</p>{% endif %}
            
            <p style="text-align: center; margin-top: 30px; font-size:0.9em; color:#666;">
                Sonuçlarınız tez çalışması kapsamında anonim olarak kaydedilmiştir.
            </p>
            <p style="text-align: center;"><a href="/" style="color:#1e88e5; text-decoration:none;"><b>Çıkış / Başa Dön</b></a></p>
        </div>
    </body>
    """
    
    return render_template_string(result_template, res1=html_s1, res2=html_s2, res3=html_s3)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
