from flask import Flask, request, render_template_string, session, redirect, url_for
import json
import os 
import logging
from datetime import datetime # Zaman damgası için

# --- YENİ EKLENTİLER (Veritabanı için) ---
from flask_sqlalchemy import SQLAlchemy
# --- BİTTİ ---

# --- YENİ EKLENTİLER (Sunucu Taraflı Oturum için) ---
import redis
from flask_session import Session
# --- BİTTİ ---

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
# GİZLİ ANAHTAR: Oturum (Session) kullanmak için gereklidir.
app.secret_key = 'BU_COK_UZUN_VE_SABIT_BIR_GIZLI_ANAHTARDIR_1234567890ABCDEF' 

# --- YENİ VERİTABANI (DATABASE) AYARLARI ---
# Render'daki 'DATABASE_URL' ortam değişkenini oku
db_uri = os.environ.get('DATABASE_URL')
# 'postgres://' URI'sini SQLAlchemy'nin anladığı 'postgresql://' formatına çevir
if db_uri and db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# --- BİTTİ ---

# --- YENİ OTURUM (SESSION) AYARLARI ---
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
try:
    redis_url = os.environ.get('REDIS_URL')
    if not redis_url:
        logging.error("HATA: REDIS_URL ortam değişkeni ayarlanmamış.")
    app.config['SESSION_REDIS'] = redis.from_url(redis_url)
    server_session = Session(app)
except Exception as e:
    logging.error(f"Redis bağlantısı kurulurken HATA oluştu: {e}")
# --- BİTTİ ---


# Soruları yükle
try:
    with open("questions.json", "r", encoding="utf-8") as f:
        QUESTIONS = json.load(f)
    TOTAL_QUESTIONS = len(QUESTIONS)
except Exception as e:
    logging.error(f"HATA: questions.json yüklenemedi: {e}")
    QUESTIONS = []
    TOTAL_QUESTIONS = 0

# --- SCHEMA_RULES (Sizin sürümünüz) ---
SCHEMA_RULES = {
    "Başarısızlık Şeması": {
        "question_ids": [5, 23, 41, 59, 77],
        "threshold": 20,
        "description": """Çocuklukta oluşumu:Sürekli kıyaslanan, yeterince takdir edilmeyen ya da başarıları küçümsenen çocuklarda gelişir. Aileden gelen “daha iyisini yapabilirdin” gibi mesajlar çocuğa sevgiyi ancak mükemmel olursa hak ettiği inancını kazandırır.<br>Yetişkinlikte:Bu şemaya sahip kişiler, içten içe “yeterince iyi değilim” düşüncesini taşırlar. İş ya da eğitim hayatında başarı elde etseler bile bunu hak ettiklerine inanmakta zorlanabilirler. Yeni bir göreve başlarken ya da önemli bir karar verirken başarısız olma korkusu belirgindir. “Ya beceremezsem, ya rezil olursam” düşünceleri onları risk almaktan uzaklaştırabilir. Bu kişiler genellikle potansiyellerinin altında performans sergilerler çünkü hata yapma ihtimali onları felç eder.<br>Bazıları mükemmeliyetçi bir çizgiye kayarak içlerindeki başarısızlık korkusunu örtmeye çalışır; sürekli çalışır, yorulur ama hiçbir zaman tatmin olmazlar. Derinlerde hep bir “bir gün herkes benim aslında o kadar da yetkin olmadığımı anlayacak” endişesi vardır."""
    },
    "Bağımlılık Şeması": {
        "question_ids": [6, 24, 60, 78],
        "threshold": 16,
        "description": """Çocuklukta oluşumu: Ebeveynlerin aşırı koruyucu, kontrolcü veya yönlendirici olduğu ailelerde görülür. Çocuk, karar alma ve deneme fırsatı bulamadığında kendi gücüne güvenmeyi öğrenemez. Ailede “sen tek başına yapamazsın, ben senin yerine hallederim” tutumu sıkça gözlemlenir.Yetişkinlikte:Bu şemaya sahip bireyler genellikle kendi kararlarını verirken tedirginlik yaşarlar. Bir işi kendi başına yapmak zorunda kaldıklarında içlerinde yoğun bir kaygı hissedebilirler. “Ya yanlış yaparsam?” düşüncesi onları sıklıkla durdurur. Çoğu zaman birine danışma, onay alma ya da destek görme ihtiyacı hissederler.İlişkilerinde aşırı bağlanma eğilimleri olabilir; partnerleri veya aileleri olmadan karar almakta zorlanırlar. Yalnız kalmak onlarda panik, kaygı ya da değersizlik duygusu yaratabilir. Dışarıdan güçlü görünseler bile içlerinde “tek başıma kalırsam kontrolü kaybederim” inancı vardır. Bu nedenle genellikle rehberlik veya yönlendirme arayışındadırlar."""
    },
    "Boyun Eğicilik Şeması": {
        "question_ids": [9, 27, 45, 63, 81],
        "threshold": 20,
        "description": """Çocuklukta oluşumu:Otoriter, cezalandırıcı veya duygusal olarak tehditkâr aile ortamlarında gelişir. Çocuk, kendi düşüncelerini savunduğunda cezalandırılacağını ya da sevgiden mahrum kalacağını öğrenir. Kabul görmek için uyum sağlaması gerektiğini hisseder.Yetişkinlikte:Bu şemaya sahip kişiler genellikle çevrelerine aşırı uyum sağlar, kendi ihtiyaçlarını bastırır ve sürekli başkalarının beklentilerini öncelerler. “Hayır” demekte güçlük çekerler çünkü reddedilmekten veya çatışmadan korkarlar. İçlerinde sıklıkla şu düşünce vardır: “Kırılmaması için sessiz kalmalıyım.”Zamanla bastırılmış öfke ve kırgınlık birikir. Dışarıdan sakin, uyumlu veya anlayışlı görünseler de iç dünyalarında “kimse beni anlamıyor, hep ben veriyorum” serzenişi vardır. İlişkilerinde kendi sınırlarını koruyamadıkları için tükenmişlik, sessiz öfke veya kendini değersiz hissetme eğilimi sık görülür.Bu şemaya sahip bireyler genellikle başkalarının onayını korumaya çalışırken kendi benliklerini arka plana atarlar. Bu da uzun vadede duygusal mesafe, bastırılmış kimlik ve içsel yalnızlık hissi yaratır."""
    },
    # ... (Diğer 14 şemanız kodun kısalığı için buraya eklenmedi,
    # ama tam kodda hepsi var) ...
    "Dayanıksızlık/Karamsarlık Şeması": {
        "question_ids": [7, 25, 79, 16, 34, 52, 88],
        "threshold": 28,
        "description": """Çocuklukta oluşumu:Olumsuzlukların sık vurgulandığı, kaygılı veya tehditkâr aile ortamlarında gelişir. Çocuk, sürekli bir tehlike beklentisiyle büyür.Yetişkinlikte:Bu şemaya sahip kişiler, hayatın kötü yanlarına odaklanma eğilimindedir. Geleceğe dair umut duymakta zorlanırlar; “bir şey iyi gidiyorsa mutlaka bozulur” düşüncesi sıktır. Genellikle felaket senaryoları kurarlar, riskten kaçınırlar.Kaygı, endişe ve güvensizlik duyguları belirgindir. İyi giden olaylarda bile “bir yerde hata olmalı” düşüncesiyle rahatlayamazlar. Bu durum, kişiyi sürekli tetikte ve yorgun hale getirir."""
    }
}


# --- YENİ VERİTABANI MODELİ (TABLOSU) ---
# Tez verilerini saklamak için bir tablo modeli tanımla
class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Demografik Bilgiler
    cinsiyet = db.Column(db.String(50))
    yas_araligi = db.Column(db.String(50))
    medeni_durum = db.Column(db.String(50))
    birlikte_yasam = db.Column(db.String(50))
    iliski_tanimi = db.Column(db.String(100))
    iliski_suresi = db.Column(db.String(50))
    terapi_destegi = db.Column(db.String(50))
    
    # Sonuçlar
    # Tetiklenen şemaları virgülle ayrılmış bir metin olarak sakla
    triggered_schemas = db.Column(db.Text) 
    # Ham cevapları JSON formatında metin olarak sakla
    all_answers_json = db.Column(db.Text)

# Veritabanı tablolarını oluşturmak için uygulama bağlamı (context)
with app.app_context():
    db.create_all()
# --- BİTTİ ---


# --- GİRİŞ SAYFASI (DEMOGRAFİK FORM İLE GÜNCELLENDİ) ---
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
        
        /* --- YENİ FORM STİLLERİ --- */
        .form-group {
            margin-bottom: 20px;
            padding: 15px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background-color: #f9f9f9;
        }
        .form-group label {
            font-weight: 600;
            display: block;
            margin-bottom: 10px;
            color: #333;
        }
        .form-options {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .form-options label {
            font-weight: 400;
            display: flex;
            align-items: center;
            background-color: #fff;
            border: 1px solid #ccc;
            border-radius: 5px;
            padding: 8px 12px;
            cursor: pointer;
            transition: background-color 0.2s, border-color 0.2s;
        }
        .form-options input[type="radio"] {
            margin-right: 8px;
            accent-color: #1e88e5;
        }
        .form-options label:hover {
            background-color: #eef8ff;
        }
        .form-options input[type="radio"]:checked + span {
            font-weight: 600;
        }
        
        /* Buton */
        .start-button {
            display: inline-block;
            width: 100%;
            padding: 15px;
            background-color: #4CAF50; /* Yeşil Buton */
            color: white;
            text-decoration: none;
            border: none;
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
            <p>Teste başlamadan önce, sizi daha iyi tanıyabilmemiz için lütfen aşağıdaki demografik bilgi formunu doldurun. Bu bilgiler, sonuçlarınızın yorumlanmasında kullanılacaktır.</p>

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

# --- BAŞLANGIÇ ROTASI (VERİLERİ SESSION'A KAYDEDİYOR) ---
@app.route("/start_test", methods=["GET", "POST"])
def start_test():
    
    # Testi başlatmadan önce oturumu temizle
    session.clear()
    
    if request.method == "POST":
        # Formdan gelen demografik verileri al ve session'a kaydet
        demographics_data = {
            'cinsiyet': request.form.get('cinsiyet'),
            'yas_araligi': request.form.get('yas_araligi'),
            'medeni_durum': request.form.get('medeni_durum'),
            'birlikte_yasam': request.form.get('birlikte_yasam'),
            'iliski_tanimi': request.form.get('iliski_tanimi'),
            'iliski_suresi': request.form.get('iliski_suresi'),
            'terapi_destegi': request.form.get('terapi_destegi')
        }
        session['demographics'] = demographics_data
    else:
        # Eğer birisi forma girmeden doğrudan /start_test'e GET yaparsa
        session['demographics'] = {} # Boş bir demografi objesi oluştur

    # Soruların yüklendiğini kontrol et
    if not QUESTIONS:
        return "HATA: Sorular yüklenemedi. Lütfen 'questions.json' dosyanızı kontrol edin.", 500
        
    # Test için oturum değişkenlerini ayarla
    session['current_question_index'] = 0
    session['answers'] = {} 
    
    return redirect(url_for('quiz'))

# --- QUIZ ROTASI ---
@app.route("/quiz", methods=["GET", "POST"])
def quiz():
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
                # Cevapları string anahtarlarla saklamak (JSON uyumluluğu için daha iyi)
                session['answers'][question_id_str] = answer_value 
                session.modified = True # Session'ın değiştiğini belirt
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


# --- SUBMIT ROTASI (YENİ: E-POSTA KALDIRILDI, VERİTABANINA KAYIT EKLENDİ) ---
@app.route("/submit")
def submit():
    scores = session.get('answers', {})
    demographics = session.get('demographics', {})
    
    if not scores:
        return redirect(url_for('index'))
    
    triggered_schemas_list = [] # Veritabanı için sadece isim listesi
    explanations_html = [] # Kullanıcının göreceği HTML listesi
    
    # --- Sonuçları Hesapla ---
    for name, rule in SCHEMA_RULES.items():
        total = sum([scores.get(str(qid), 0) for qid in rule["question_ids"]])
        
        if total >= rule["threshold"]:
            triggered_schemas_list.append(name) # Veritabanına eklenecek
            
            # Kullanıcının göreceği akordiyon kartını oluştur
            card_html = f"""
            <div class="schema-card">
                <details>
                    <summary>{name}</summary>
                    <div class="details-content">
                        <p>{rule['description']}</p>
                    </div>
                </details>
            </div>
            """
            explanations_html.append(card_html)

    # --- YENİ: Veritabanına Kaydet ---
    try:
        new_result = TestResult(
            # Demografik bilgileri session'dan al
            cinsiyet=demographics.get('cinsiyet'),
            yas_araligi=demographics.get('yas_araligi'),
            medeni_durum=demographics.get('medeni_durum'),
            birlikte_yasam=demographics.get('birlikte_yasam'),
            iliski_tanimi=demographics.get('iliski_tanimi'),
            iliski_suresi=demographics.get('iliski_suresi'),
            terapi_destegi=demographics.get('terapi_destegi'),
            
            # Sonuçları kaydet
            triggered_schemas=", ".join(triggered_schemas_list), # Listeyi virgüllü metne çevir
            all_answers_json=json.dumps(scores, ensure_ascii=False) # Ham veriyi JSON metni olarak kaydet
        )
        
        db.session.add(new_result)
        db.session.commit()
        logging.info("Yeni test sonucu başarıyla veritabanına kaydedildi.")
        
    except Exception as e:
        logging.error(f"Veritabanına kayıt sırasında HATA oluştu: {e}")
        db.session.rollback() # Hata olursa işlemi geri al
        # Veritabanı çökse bile kullanıcının sonuçları görmesine izin ver
        

    # --- Kullanıcıya Gösterilecek HTML'i Hazırla ---
    
    result_template = """
    <!doctype html>
    <title>Young Şema Testi - Sonuç</title>
    <style>
        {% raw %}
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; color: #333; text-align: center; }
        .container { max-width: 600px; margin: 0 auto; background-color: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08); text-align: left; }
        
        /* Ana Başlık */
        h2 { color: #1e88e5; text-align: center; margin-bottom: 20px; }
        
        /* "Tetiklenen Şemalar:" Başlığı */
        h3.section-title {
            color: #333;
            border-bottom: 1px solid #ccc;
            padding-bottom: 5px;
            margin-top: 10px;
            text-align: left;
            font-size: 1.3em;
        }

        /* --- Yeni Akordiyon Stilleri --- */
        .schema-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            margin-bottom: 15px;
            background-color: #ffffff;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: box-shadow 0.2s;
        }
        .schema-card:hover {
            box-shadow: 0 4px 8px rgba(0,0,0,0.08);
        }
        
        details {
            font-family: inherit;
        }
        
        /* Tıklanabilir başlık (Kırmızı Şema Adı) */
        summary {
            padding: 16px 20px;
            cursor: pointer;
            font-size: 1.2em;
            font-weight: 600;
            color: #e53935; /* Kırmızı Şema Başlığı */
            list-style: none; /* Varsayılan oku kaldır */
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        summary::-webkit-details-marker { display: none; }
        
        /* Tıklanabilir + / - ikonu */
        summary::after {
            content: '+';
            font-size: 1.5em;
            font-weight: 300;
            color: #1e88e5; /* Mavi Artı */
            transition: transform 0.2s;
        }
        details[open] summary {
            border-bottom: 1px solid #eee;
        }
        details[open] summary::after {
            content: '−'; /* Eksi ikonu */
        }

        /* Açılan içerik alanı */
        .details-content {
            padding: 16px 20px;
            border-top: 1px solid #eee;
            line-height: 1.6;
            color: #333;
        }
        /* --- Bitiş: Yeni Stiller --- */

        p { line-height: 1.6; }
        a { display: inline-block; margin-top: 20px; padding: 10px 20px; background-color: #1e88e5; color: white; text-decoration: none; border-radius: 8px; transition: background-color 0.3s; }
        a:hover { background-color: #1565c0; }
        {% endraw %}
    </style>
    <body>
        <div class="container">
            <h2>Young Şema Testi Sonuçları</h2>
            
            {{ result_content | safe }}
            
            <p style="text-align: center; margin-top: 20px;">
                <strong>Teşekkürler!</strong> Sonuçlarınız tez çalışması için anonim olarak kaydedilmiştir.
            </p>
            <p style="text-align: center;"><a href="/">Yeniden Başla</a></p>
        </div>
    </body>
    """
    
    # Dinamik içerik oluşturuluyor
    result_content = ""
    if explanations_html:
        # YENİ: Başlığı ve kartları ayır
        result_content += '<h3 class="section-title">Tetiklenen Şemalar:</h3>'
        result_content += "".join(explanations_html)
    else:
        result_content += "<p>Tebrikler! Belirgin olarak tetiklenmiş bir şema tespit edilmedi.</p>"
    
    result_content += f'<p style="text-align:center; margin-top: 20px;">Toplam Cevaplanan Soru: {len(scores)}/{TOTAL_QUESTIONS}</p>'
    
    
    # --- DÜZELTME (BENİM HATAM): 'result_template' değişkenini ekle ---
    return render_template_string(
        result_template,
        result_content=result_content
    )
# --- DÜZELTME BİTTİ ---


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
