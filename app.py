from flask import Flask, request, render_template_string, session, redirect, url_for
import json
import os 
import logging
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import redis
from flask_session import Session
import requests # API isteği için gerekli

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
# (Buradaki kurallarınız aynı kalıyor, kod kalabalığı olmaması için özet geçiyorum
# ama siz KESİNLİKLE kendi app.py dosyanızdaki kuralları koruyun veya 
# önceki cevabımdaki tam kuralları buraya yapıştırın.)

# 1. AŞAMA (Önceki kodunuzdaki kuralların aynısı olmalı)
SCHEMA_RULES_STAGE_1 = {
    "Duygusal Yoksunluk": { "question_ids": [1, 19, 37, 55, 73], "threshold": 20, "description": "..." },
    "Terk Edilme": { "question_ids": [2, 20, 38, 56, 74], "threshold": 20, "description": "..." },
    # ... (Lütfen buraya önceki kodunuzdaki TÜM şemaları eksiksiz yapıştırın) ...
    "Ekonomik Dayanıksızlık": { "question_ids": [62, 71], "threshold": 8, "description": "..." }
}

# 2. AŞAMA
COPING_RULES_STAGE_2 = {
    "Aşırı Telafi": { "question_ids": [1, 5, 8, 10], "threshold": 16, "description": "..." },
    "Teslim": { "question_ids": [2, 6, 9, 11], "threshold": 16, "description": "..." },
    "Kaçınma": { "question_ids": [3, 4, 7, 12], "threshold": 16, "description": "..." }
}

# 3. AŞAMA
RULES_STAGE_3 = {
    "Çift Uyumu": { "question_ids": list(range(1, 15)), "threshold": 0, "description": "" }
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
    all_answers_json = db.Column(db.Text)

with app.app_context():
    db.create_all()

# --- YENİ: E-POSTA GÖNDERME FONKSİYONU (BREVO API) ---
def send_report_via_brevo(demog, res1_names, res2_names, res3_text):
    api_key = os.environ.get('BREVO_API_KEY')
    # Eğer API anahtarı yoksa fonksiyon çalışmaz (hata vermez, sadece göndermez)
    if not api_key:
        logging.warning("Brevo API anahtarı bulunamadı, e-posta gönderilmedi.")
        return

    # Rapor HTML İçeriği (Tablo formatında)
    html_content = f"""
    <html>
    <body>
        <h2 style="color:#1e88e5;">Yeni Test Raporu</h2>
        <p><strong>Tarih:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
        
        <h3 style="border-bottom:1px solid #ccc;">1. Demografik Bilgiler</h3>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse:collapse; width:100%;">
            <tr><td style="background:#f9f9f9;"><b>Cinsiyet</b></td><td>{demog.get('cinsiyet')}</td></tr>
            <tr><td style="background:#f9f9f9;"><b>Yaş Aralığı</b></td><td>{demog.get('yas_araligi')}</td></tr>
            <tr><td style="background:#f9f9f9;"><b>Medeni Durum</b></td><td>{demog.get('medeni_durum')}</td></tr>
            <tr><td style="background:#f9f9f9;"><b>İlişki Süresi</b></td><td>{demog.get('iliski_suresi')}</td></tr>
            <tr><td style="background:#f9f9f9;"><b>Terapi Desteği</b></td><td>{demog.get('terapi_destegi')}</td></tr>
        </table>
        
        <h3 style="border-bottom:1px solid #ccc; margin-top:20px;">2. Test Sonuçları</h3>
        
        <p><strong>Bölüm 1: Tetiklenen Şemalar</strong></p>
        <ul>
            {''.join([f'<li>{name}</li>' for name in res1_names]) if res1_names else '<li>Tetiklenen şema yok.</li>'}
        </ul>
        
        <p><strong>Bölüm 2: Başa Çıkma Biçimleri</strong></p>
        <ul>
            {''.join([f'<li>{name}</li>' for name in res2_names]) if res2_names else '<li>Belirgin biçim yok.</li>'}
        </ul>
        
        <p><strong>Bölüm 3: Çift Uyumu</strong></p>
        <div style="background:#eef8ff; padding:10px; border-left:4px solid #1e88e5;">
            {res3_text}
        </div>
        
        <br>
        <p style="font-size:12px; color:#888;">Bu e-posta Vitalis Kişilik Testi sistemi tarafından otomatik oluşturulmuştur.</p>
    </body>
    </html>
    """

    # API İsteği
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    # Alıcı adresi (Render Environment'tan alıyoruz, yoksa kendinize gönderin)
    receiver_email = os.environ.get('EMAIL_RECEIVER', 'tez.verilerim@gmail.com') 
    
    payload = {
        "sender": {"name": "Vitalis Test Sistemi", "email": "no-reply@vitalis.com"},
        "to": [{"email": receiver_email}],
        "subject": f"Test Sonucu Raporu - {demog.get('cinsiyet')} - {demog.get('yas_araligi')}",
        "htmlContent": html_content
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 201:
            logging.info("Rapor e-postası başarıyla gönderildi.")
        else:
            logging.error(f"E-posta gönderilemedi: {response.text}")
    except Exception as e:
        logging.error(f"API Bağlantı Hatası: {e}")

# --- ROTALAR (INDEX, START_TEST, QUIZ AYNI - DEĞİŞMEDİ) ---
# (Lütfen mevcut app.py dosyanızdaki index, start_test, quiz rotalarını koruyun. 
# Sadece aşağıda değiştirdiğimiz SUBMIT fonksiyonunu ve yukarıdaki send_report fonksiyonunu eklemeniz yeterli.)

@app.route("/")
def index():
    # (Mevcut kodunuzu kullanın)
    return render_template_string(...) 

@app.route("/start_test", methods=["GET", "POST"])
def start_test():
    # (Mevcut kodunuzu kullanın)
    return redirect(url_for('quiz'))
    
# ... (start_stage_2, start_stage_3 ve quiz fonksiyonları aynen kalacak) ...
@app.route("/start_stage_2"):
    return redirect(url_for('quiz'))
@app.route("/start_stage_3"):
    return redirect(url_for('quiz'))
@app.route("/quiz", methods=["GET", "POST"]):
    # (Mevcut kodunuz)
    return render_template_string(...)

# --- GÜNCELLENEN SUBMIT ROTASI ---
@app.route("/submit")
def submit():
    s1 = session.get('answers_stage1', {})
    s2 = session.get('answers_stage2', {})
    s3 = session.get('answers_stage3', {})
    demog = session.get('demographics', {})
    
    html_s1, html_s2, html_s3 = [], [], []
    db_s1, db_s2, db_s3 = [], [], [] # Veritabanı ve E-posta için temiz isim listeleri

    # --- 1. AŞAMA ---
    for name, rule in SCHEMA_RULES_STAGE_1.items():
        total = sum([s1.get(str(qid), 0) for qid in rule["question_ids"]])
        if total >= rule["threshold"]:
            db_s1.append(name)
            html_s1.append(f"<div class='schema-card'><details><summary>{name}</summary><div class='details-content'><p>{rule['description']}</p></div></details></div>")

    # --- 2. AŞAMA ---
    for name, rule in COPING_RULES_STAGE_2.items():
        total = sum([s2.get(str(qid), 0) for qid in rule["question_ids"]])
        if total >= rule["threshold"]:
            db_s2.append(name)
            html_s2.append(f"<div class='schema-card'><details><summary>{name}</summary><div class='details-content'><p>{rule['description']}</p></div></details></div>")

    # --- 3. AŞAMA ---
    total_score_3 = 0
    for qid in range(1, 15):
        raw_score = s3.get(str(qid), 0)
        if raw_score == 0: continue
        if 7 <= qid <= 14: score = 6 - raw_score
        else: score = raw_score
        total_score_3 += score
    
    uyum_sonuc = "İlişki Çift Uyumunuz: %50'nin Üzerindedir" if total_score_3 >= 35 else "İlişki Çift Uyumunuz: %50'nin Altındadır"
    db_s3.append(uyum_sonuc)
    html_s3.append(f"<div class='schema-card'><div style='padding:15px;'><b>{uyum_sonuc}</b></div></div>")

    # --- 1. VERİTABANINA KAYIT ---
    try:
        new_result = TestResult(
            cinsiyet=demog.get('cinsiyet'),
            yas_araligi=demog.get('yas_araligi'),
            medeni_durum=demog.get('medeni_durum'),
            birlikte_yasam=demog.get('birlikte_yasam'),
            iliski_tanimi=demog.get('iliski_tanimi'),
            iliski_suresi=demog.get('iliski_suresi'),
            terapi_destegi=demog.get('terapi_destegi'),
            triggered_stage1=" | ".join(db_s1), 
            triggered_stage2=" | ".join(db_s2),
            triggered_stage3=" | ".join(db_s3),
            all_answers_json=json.dumps({"s1":s1, "s2":s2, "s3":s3})
        )
        db.session.add(new_result)
        db.session.commit()
    except Exception as e:
        logging.error(f"Kayıt Hatası: {e}")

    # --- 2. E-POSTA RAPORU GÖNDER (YENİ) ---
    # Bu işlem sunucuyu yavaşlatmasın diye en sonda ve hata yakalayarak yapıyoruz
    try:
        send_report_via_brevo(demog, db_s1, db_s2, uyum_sonuc)
    except Exception as e:
        logging.error(f"Rapor Gönderme Hatası: {e}")

    # --- 3. KULLANICI EKRANI ---
    # (Mevcut result_template kodunuz buraya gelecek)
    result_template = """<!doctype html>...""" # (Önceki koddaki gibi)
    
    return render_template_string(result_template, res1=html_s1, res2=html_s2, res3=html_s3)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
