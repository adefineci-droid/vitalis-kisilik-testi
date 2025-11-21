from flask import Flask, request, render_template_string, session, redirect, url_for, Response
import json
import os 
import logging
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import redis
from flask_session import Session
import requests # Brevo API için
import csv
import io

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = 'BU_COK_UZUN_VE_SABIT_BIR_GIZLI_ANAHTARDIR_1234567890ABCDEF' 

# --- ADMIN PANELİ ŞİFRESİ (Değiştirebilirsiniz) ---
ADMIN_PASSWORD = "tez-admin-giris"

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


# --- E-POSTA GÖNDERME FONKSİYONU ---
def send_report_via_brevo(demog, res1_names, res2_names, res3_text, subject_no):
    api_key = os.environ.get('BREVO_API_KEY')
    
    if not api_key:
        logging.warning("Brevo API anahtarı bulunamadı, e-posta gönderilmedi.")
        return

    # Rapor HTML İçeriği
    html_content = f"""
    <html>
    <body>
        <h2 style="color:#1e88e5;">Yeni Test Raporu (Katılımcı No: {subject_no})</h2>
        <p><strong>Tarih:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
        <p><strong>Katılımcı Numarası:</strong> <span style="font-size:1.2em; font-weight:bold;">{subject_no}</span></p>
        
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

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json"
    }
    
    receiver_email = os.environ.get('EMAIL_RECEIVER', 'tez.verilerim@gmail.com') 
    
    # Gönderici olarak alıcı adresini kullanıyoruz (Brevo onayı için)
    sender_email = receiver_email 
    
    payload = {
        "sender": {"name": "Vitalis Test Sistemi", "email": sender_email},
        "to": [{"email": receiver_email}],
        "subject": f"Test Raporu - Katılımcı {subject_no} - {demog.get('cinsiyet')}",
        "htmlContent": html_content
    }

    try:
        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        logging.error(f"API Bağlantı Hatası: {e}")


# --- KURALLAR (TAM VE EKSİKSİZ) ---

# 1. AŞAMA: ŞEMALAR
SCHEMA_RULES_STAGE_1 = {
    "Duygusal Yoksunluk": { "question_ids": [1, 19, 37, 55, 73], "threshold": 20, "description": """Duygusal Yoksunluk Şeması:Çocuklukta oluşumu:Sevgi, ilgi ya da empati gibi temel duygusal gereksinimlerin karşılanmadığı ortamlarda gelişir. Çocuk, isteklerine cevap alamadıkça duygusal ihtiyaçların önemsiz olduğuna inanabilir.<br>Yetişkinlikte:Bu şemaya sahip kişiler genellikle “kimse beni gerçekten anlamıyor” duygusunu taşırlar. İlişkilerinde hep bir eksiklik hisseder, karşısındakinin sevgisini tam olarak hissedemezler. Partnerleri onları sevse bile, içten içe “benim duygularımı anlamıyor” diye düşünürler. Bu hissetme biçimi, çoğu zaman çocuklukta ihtiyaç duyulan şefkatin yokluğundan beslenir.<br>Bazı kişiler bu boşlukla başa çıkmak için duygusal yakınlıktan tamamen kaçınabilir — soğuk ve mesafeli görünebilirler. Bazıları ise çok fazla bağlanarak içlerindeki açlığı doldurmaya çalışırlar. Her iki durumda da temel inanç şudur: “Kimse beni gerçekten anlamaz.""" },
    "Terk Edilme": { "question_ids": [2, 20, 38, 56, 74], "threshold": 20, "description": """Terk Edilme Şeması:Çocuklukta oluşumu:Sık taşınmalar, ayrılıklar, boşanma ya da ebeveynin duygusal olarak erişilemez olduğu durumlar bu şemayı oluşturabilir. Çocuk, kendini sevilen ama her an kaybedilebilecek biri olarak algılar.<br>Yetişkinlikte:Terk edilme şeması olan bireyler, yakın ilişkilerde yoğun kaybetme korkusu yaşarlar. Partnerleri bir süre sessiz kaldığında bile “beni artık istemiyor” kaygısı doğabilir. Küçük ilgisizlikleri büyük tehdit gibi algılarlar ve duygusal dalgalanmalar sıklıkla görülür.<br>Bazıları terk edilmemek için fazlasıyla yapışkan, bazıları ise “nasıl olsa giderler” düşüncesiyle mesafeli ve soğuk davranabilir. İlişkilerinde gerçek yakınlık istedikleri halde, bu yakınlık onlarda kaygı yaratır. Sıklıkla “ya benim için burada kalmazsa?” düşüncesi eşlik eder.""" },
    "Kuşkuculuk": { "question_ids": [3, 21, 39, 57, 75, 44], "threshold": 24, "description": """Kuşkuculuk Şeması:Çocuklukta oluşumu:İhmal, aldatılma, cezalandırılma ya da sözel-fiziksel istismar deneyimleri sonucu gelişir. Çocuk, “insanlara güvenilmez” inancını öğrenir.<br>Yetişkinlikte:Kuşkuculuk şeması olan kişiler, başkalarının niyetlerinden kolayca şüphe duyarlar. “Kesin bir çıkarı var” ya da “beni bir gün incitecek” düşünceleri akıllarının bir köşesindedir. Bu kişiler çoğu zaman güven duygusunu kontrol altında tutarak sağlarlar: mesafe koymak, sınır çizmek, her şeyi denetlemek gibi.<br>İlişkilerinde tam bir teslimiyet veya yakınlık kurmak zor gelir. Çünkü zihinlerinde “çok yakınlaşırsam canım yanar” inancı vardır. Bu durum, samimiyet arzusu ile güven korkusu arasında bir gelgit yaratır.""" },
    "Sosyal İzolasyon": { "question_ids": [4, 40, 58, 76], "threshold": 16, "description": """Sosyal İzolasyon Şeması:Çocuklukta oluşumu:Aile içinde ya da okulda dışlanma, farklı hissettirilme ya da aidiyetin zayıf olduğu ortamlar bu şemayı besler. Çocuk kendini toplumdan ayrı ve anlaşılmamış hisseder.<br>Yetişkinlikte:Bu şemaya sahip kişiler çoğu zaman “ben onlardan değilim” düşüncesini taşırlar. Sosyal ortamlarda güvensiz hissedebilir, kalabalıklar içinde bile yalnızlık yaşayabilirler. Diğerlerinin onları yargılayacağı veya reddedeceği korkusuyla kendilerini geri çekerler.<br>Bazıları “ben zaten uymam” diye yakınlaşmaktan kaçınırken, bazıları katı bir uyum maskesi takabilir. İçlerinde sıklıkla ait olma arzusu vardır ama bu arzu “nasıl olsa anlamayacaklar” düşüncesiyle örtülüdür.""" },
    "Kusurluluk": { "question_ids": [5, 23, 41, 59, 77, 43, 90], "threshold": 28, "description": """Kusurluluk Şeması:Çocuklukta oluşumu:Sürekli eleştirilen, reddedilen ya da başkalarıyla kıyaslanan çocuklarda gelişir. Çocuk, sevgiyi koşullu olarak alabileceğini öğrenir: “Hatalıysam sevilmem.”<br>Yetişkinlikte:Kusurluluk şeması olan kişiler içten içe “bende bir yanlışlık var” duygusunu taşırlar. Başkalarının onları sevmesinin zor olduğunu düşünürler. İlişkilerde eleştiriye çok duyarlıdırlar; küçük bir yorum bile içlerinde büyük bir utanç yaratabilir. Bu kişiler genellikle kusurlarını gizlemeye, hatalarını örtmeye çalışır.<br>Bir yandan da sürekli olarak onay ararlar — sevilmek, kabul edilmek ve “yeterli” olduklarını duymak isterler. Ancak içlerindeki ses “yine de eksiksin” der. Bu nedenle kimi zaman geri çekilme, kimi zaman da sürekli kendini kanıtlama davranışları görülür. Kendilerini başkalarıyla kıyaslama, değersiz hissetme ve beğenilmeye çalışma çabaları sıktır.""" },
    "Başarısızlık": { "question_ids": [6, 24, 42, 60, 78], "threshold": 20, "description": """Başarısızlık Şeması;Çocuklukta oluşumu:Sürekli kıyaslanan, yeterince takdir edilmeyen ya da başarıları küçümsenen çocuklarda gelişir. Aileden gelen “daha iyisini yapabilirdin” gibi mesajlar çocuğa sevgiyi ancak mükemmel olursa hak ettiği inancını kazandırır.<br>Yetişkinlikte:Bu şemaya sahip kişiler, içten içe “yeterince iyi değilim” düşüncesini taşırlar. İş ya da eğitim hayatında başarı elde etseler bile bunu hak ettiklerine inanmakta zorlanabilirler. Yeni bir göreve başlarken ya da önemli bir karar verirken başarısız olma korkusu belirgindir. “Ya beceremezsem, ya rezil olursam” düşünceleri onları risk almaktan uzaklaştırabilir. Bu kişiler genellikle potansiyellerinin altında performans sergilerler çünkü hata yapma ihtimali onları felç eder.<br>Bazıları mükemmeliyetçi bir çizgiye kayarak içlerindeki başarısızlık korkusunu örtmeye çalışır; sürekli çalışır, yorulur ama hiçbir zaman tatmin olmazlar. Derinlerde hep bir “bir gün herkes benim aslında o kadar da yetkin olmadığımı anlayacak” endişesi vardır.""" },
    "Bağımlılık": { "question_ids": [7, 25, 61, 79], "threshold": 16, "description": """Bağımlılık Şeması:Çocuklukta oluşumu: Ebeveynlerin aşırı koruyucu, kontrolcü veya yönlendirici olduğu ailelerde görülür. Çocuk, karar alma ve deneme fırsatı bulamadığında kendi gücüne güvenmeyi öğrenemez. Ailede “sen tek başına yapamazsın, ben senin yerine hallederim” tutumu sıkça gözlemlenir.<br>Yetişkinlikte:Bu şemaya sahip bireyler genellikle kendi kararlarını verirken tedirginlik yaşarlar. Bir işi kendi başına yapmak zorunda kaldıklarında içlerinde yoğun bir kaygı hissedebilirler. “Ya yanlış yaparsam?” düşüncesi onları sıklıkla durdurur. Çoğu zaman birine danışma, onay alma ya da destek görme ihtiyacı hissederler.<br>İlişkilerinde aşırı bağlanma eğilimleri olabilir; partnerleri veya aileleri olmadan karar almakta zorlanırlar. Yalnız kalmak onlarda panik, kaygı ya da değersizlik duygusu yaratabilir. Dışarıdan güçlü görünseler bile içlerinde “tek başıma kalırsam kontrolü kaybederim” inancı vardır. Bu nedenle genellikle rehberlik veya yönlendirme arayışındadırlar.""" },
    "Dayanıksızlık": { "question_ids": [8, 26, 80, 17, 35, 53, 89], "threshold": 28, "description": """Dayanıksızlık / Karamsarlık Şeması:Çocuklukta oluşumu:Olumsuzlukların sık vurgulandığı, kaygılı veya tehditkâr aile ortamlarında gelişir. Çocuk, sürekli bir tehlike beklentisiyle büyür.<br>Yetişkinlikte:Bu şemaya sahip kişiler, hayatın kötü yanlarına odaklanma eğilimindedir. Geleceğe dair umut duymakta zorlanırlar; “bir şey iyi gidiyorsa mutlaka bozulur” düşüncesi sıktır. Genellikle felaket senaryoları kurarlar, riskten kaçınırlar.<br>Kaygı, endişe ve güvensizlik duyguları belirgindir. İyi giden olaylarda bile “bir yerde hata olmalı” düşüncesiyle rahatlayamazlar. Bu durum, kişiyi sürekli tetikte ve yorgun hale getirir.""" },
    "İç İçelik": { "question_ids": [9, 27, 45, 63, 81], "threshold": 20, "description": """İç İçelik (Gelişmemiş Benlik) Şeması:Çocuklukta oluşumu:Bu şema genellikle ebeveynle aşırı yakın ve duygusal bağımlılığın olduğu ailelerde gelişir. Çocuğun kendi tercihlerine ve duygularına alan tanınmaz; ebeveyn çoğu kararı onun yerine verir. “Ben senin için yaşıyorum” gibi ifadeler, çocuğun kendini ebeveynin devamı gibi görmesine neden olur.<br>Yetişkinlikte:Bu şemaya sahip kişiler ilişkilerinde sıklıkla aşırı bağlılık ve duygusal bağımlılık geliştirirler. “Onsuz yaşayamam” veya “o olmayan bir hayat anlamsız” gibi düşünceler yoğundur. Partnerinin ya da aile üyesinin duygusal durumu, kendi duygusal halini belirleyebilir.<br>Zaman zaman kendi istekleriyle yakınlarının isteklerini karıştırır; nerede bittiğini, karşısındakinin nerede başladığını ayırt etmekte zorlanır. Kendi yaşam kararlarını alırken “ya onu üzersen?” endişesi baskın hale gelebilir. İlişkiler kopmaya yöneldiğinde yoğun kaygı, boşluk ve yalnızlık duyguları yaşanabilir.""" },
    "Boyun Eğicilik": { "question_ids": [10, 28, 46, 64, 82], "threshold": 20, "description": """Boyun Eğicilik Şeması:Çocuklukta oluşumu:Otoriter, cezalandırıcı veya duygusal olarak tehditkâr aile ortamlarında gelişir. Çocuk, kendi düşüncelerini savunduğunda cezalandırılacağını ya da sevgiden mahrum kalacağını öğrenir. Kabul görmek için uyum sağlaması gerektiğini hisseder.<br>Yetişkinlikte:Bu şemaya sahip kişiler genellikle çevrelerine aşırı uyum sağlar, kendi ihtiyaçlarını bastırır ve sürekli başkalarının beklentilerini öncelerler. “Hayır” demekte güçlük çekerler çünkü reddedilmekten veya çatışmadan korkarlar. İçlerinde sıklıkla şu düşünce vardır: “Kırılmaması için sessiz kalmalıyım.”<br>Zamanla bastırılmış öfke ve kırgınlık birikir. Dışarıdan sakin, uyumlu veya anlayışlı görünseler de iç dünyalarında “kimse beni anlamıyor, hep ben veriyorum” serzenişi vardır. İlişkilerinde kendi sınırlarını koruyamadıkları için tükenmişlik, sessiz öfke veya kendini değersiz hissetme eğilimi sık görülür.Bu şemaya sahip bireyler genellikle başkalarının onayını korumaya çalışırken kendi benliklerini arka plana atarlar. Bu da uzun vadede duygusal mesafe, bastırılmış kimlik ve içsel yalnızlık hissi yaratır.""" },
    "Kendini Feda": { "question_ids": [11, 29, 47, 65, 83], "threshold": 20, "description": """Kendini Feda Şeması:Çocuklukta oluşumu:Ailenin ihtiyaçlarının ön planda olduğu, çocuğun kendi duygularını ifade edemediği ailelerde gelişir. Çocuk, sevgiyi “fedakârlık yaparak” kazandığını öğrenir.<br>Yetişkinlikte:Bu şemaya sahip bireyler başkalarının mutluluğu için kendi isteklerinden vazgeçme eğilimindedirler. “Önce onlar iyi olsun” düşüncesiyle yaşarlar. Yardımsever, duyarlı ve fedakârdırlar ancak içten içe “benimle kim ilgilenecek?” sorusu yankılanır.<br>Zamanla kendi ihtiyaçlarını bastırdıkları için yorgunluk, tükenmişlik ve kırgınlık hissederler. Duygusal olarak sevilmek ve görülmek isteseler de bunu dile getirmekte zorlanırlar. Sessiz bir beklentiyle, başkalarının fark etmesini umut ederler.""" },
    "Duyguları Bastırma": { "question_ids": [12, 30, 48, 66, 84], "threshold": 20, "description": """Duyguları Bastırma Şeması:Çocuklukta oluşumu:Duyguların açıkça ifade edilmediği, duygusallığın zayıflık olarak görüldüğü ailelerde gelişir. Çocuk öfkesini, korkusunu veya sevgisini gösterdiğinde ayıplanmış ya da cezalandırılmış olabilir.<br>Yetişkinlikte:Bu şemaya sahip kişiler duygularını göstermekten çekinirler. Ağlamayı, yardım istemeyi veya zayıf görünmeyi sevmeyebilirler. Dışarıdan soğukkanlı ve kontrollü görünseler de içlerinde yoğun duygusal gerilim taşırlar.<br>İlişkilerinde duygusal yakınlıktan kaçınabilirler; çünkü duygularını açarlarsa “fazla hassas” ya da “güçsüz” görüneceklerinden korkarlar. Bazen öfke, üzüntü ya da sevgi yerine mantık ve kontrol ön plana çıkar. Zihinsel olarak yakın olsalar bile duygusal bağ kurmakta zorlanabilirler.""" },
    "Statü Arayıcılık": { "question_ids": [13, 31, 14, 16, 34, 52, 70, 88], "threshold": 32, "description": """Statü Arayıcılık Şeması:Çocuklukta oluşumu:Ailenin başarı, mevki, statü ya da görünüşe fazla önem verdiği durumlarda gelişir. Çocuk, sevginin “başarıyla kazanılan” bir şey olduğuna inanır.<br>Yetişkinlikte:Bu şemaya sahip kişiler değeri içsel özelliklerinden çok dışsal başarılarla ölçer. “Eğer başarılıysam, önemliyim.” düşüncesi baskındır. Hayatlarında sürekli bir yarış hissi vardır; daha fazla çalışır, daha fazla kazanır ama hiçbir zaman yeterli hissetmezler.<br>Başarısız olduklarında veya takdir görmediklerinde yoğun değersizlik yaşarlar. Duygusal ilişkilerde de kendilerini statüyle tanımlarlar: partnerlerinin “gözünde yükselmek” onlar için önemlidir. Yorgun, tatminsiz ve sürekli hedef peşinde koşan bir ruh hali hâkimdir.""" },
    "Yetersiz Özdenetim": { "question_ids": [15, 33, 51, 69, 87], "threshold": 20, "description": """Yetersiz Özdenetim Şeması:Çocuklukta oluşumu:Kuralların net olmadığı, çocuğa sınır koyulmayan ya da duygusal olarak aşırı serbest bırakılan ailelerde ortaya çıkar. Çocuk, dürtülerini düzenlemeyi ve sorumluluk almayı öğrenemez.<br>Yetişkinlikte:Bu şemaya sahip bireyler genellikle anlık isteklerine göre hareket ederler. Sabırsız, ertesi günü düşünmeden karar veren ya da sık sık “dayanamayıp” sınırlarını aşan davranışlar gösterebilirler. Öz disiplin gerektiren durumlarda (örneğin düzenli çalışma, diyet, bir alışkanlığı bırakma) zorlanırlar.<br>İçlerinde çoğu zaman “bunu şimdi istiyorum” duygusu baskındır. Bu kişiler için duygusal ya da fiziksel haz anı, uzun vadeli hedeflerin önüne geçer. Duygusal tepkileri de yoğun olabilir; öfke, hayal kırıklığı veya keyif duygusu hızla değişir.""" },
    "Büyüklenmecilik": { "question_ids": [22, 32, 50, 68, 86], "threshold": 20, "description": """Büyüklenmecilik Şeması:Çocuklukta oluşumu:Sınırların çizilmediği, çocuğun her isteğinin karşılandığı, kuralların belirsiz olduğu ailelerde gelişebilir. Bazen de tam tersi biçimde, değersiz hissettirilen çocuk “üstünlük duygusunu” bir savunma olarak geliştirebilir.<br>Yetişkinlikte:Bu şemaya sahip kişiler genellikle kendilerini özel veya ayrıcalıklı hissederler. “Kurallar herkes için geçerli ama benim için değil.” düşüncesi baskındır. Kimi zaman başkalarının sınırlarına saygı göstermekte zorlanabilirler. Eleştiriye kapalıdırlar ve yanıldıklarını kabul etmekte güçlük çekerler.<br>Yine de bu tutumun altında çoğu zaman derin bir görülme ve onaylanma ihtiyacı yatar. Başkalarından takdir almadıklarında değersizlik hissi yüzeye çıkar. Duygusal olarak savunmacı, bazen kibirli görünseler de aslında içlerinde kırılgan bir “beğenilme arzusu” taşırlar.""" },
    "Cezalandırıcılık": { "question_ids": [49, 67, 85, 18, 36, 59, 72], "threshold": 28, "description": """Cezalandırıcılık ŞemasıÇocuklukta oluşumu:Hataların sert şekilde eleştirildiği veya cezalandırıldığı ortamlarda gelişir. Çocuk, kusursuz olmanın tek kabul edilme yolu olduğuna inanır.<br>Yetişkinlikte:Bu şemaya sahip kişiler hata yapanlara karşı katı ve affetmez bir tutum sergileyebilir. Aynı sertliği kendilerine de gösterirler; bir hata yaptıklarında uzun süre kendilerini suçlar, pişmanlık hissederler. İçlerinde “yanlış yapan bedel ödemeli” inancı vardır.<br>Bu kişiler genellikle vicdan sahibi ve yüksek sorumluluk duygusuna sahip olsalar da kendilerine karşı anlayışsızdırlar. Duygusal esneklikleri azdır; iç dünyalarında “ya hata yaparsam?” korkusu baskındır.""" },
    "Ekonomik Dayanıksızlık": { "question_ids": [62, 71], "threshold": 8, "description": """Ekonomik Dayanıksızlık Şeması:Çocuklukta oluşumu:Maddi belirsizliklerin, yoksunlukların veya güvensizliğin yaşandığı ailelerde görülür. Çocuk, güvenli bir ortamın ancak maddi istikrarla mümkün olduğuna inanır.<br>Yetişkinlikte:Bu şemaya sahip bireyler, parasal konulara ilişkin sürekli bir “kaybetme” endişesi taşırlar. Mali durumu iyi olsa bile içlerinde “her an her şey bitebilir” korkusu vardır. Para biriktirme, tasarruf yapma ya da “kıtlık bilinciyle yaşama” eğilimleri görülür.<br>Maddi güvenlik sağlanamadığında huzurları kaçar; güven duygusunu genellikle dışsal koşullara bağlarlar. Bu kişiler için “rahatlama” hissi, geleceğe dair kontrol duygusuyla birlikte gelir.""" }
}

# 2. AŞAMA: BAŞA ÇIKMA
COPING_RULES_STAGE_2 = {
    "Aşırı Telafi": { 
        "question_ids": [1, 5, 8, 10], 
        "threshold": 16, 
        "description": """Aşırı Telafi Etme: Aşırı telafi biçiminde kişi, şemanın öne sürdüğü olumsuz inançların tam tersini göstermeye çalışarak şemayla savaşır. “Yetersizim” şemasına karşı mükemmeliyetçilik, “değersizim” şemasına karşı kontrolcü veya üstün davranışlar gelişebilir. Bu durum kısa vadede güç hissi verebilir, ancak uzun vadede gerginlik ve ilişkilerde mesafe yaratabilir."""
    },
    "Teslim": { 
        "question_ids": [2, 6, 9, 11], 
        "threshold": 16, 
        "description": """Şemaya Teslim Olma: Bu biçimde kişi, sahip olduğu olumsuz inançların doğru olduğuna inanır ve bu inançlara uygun davranır. “Ben değersizim”, “Kimse beni sevmez” gibi düşünceler davranışlarını yönlendirebilir. Bu durum kısa vadede uyum sağlasa da uzun vadede özsaygıyı zedeleyebilir."""
    },
    "Kaçınma": { 
        "question_ids": [3, 4, 7, 12], 
        "threshold": 16, 
        "description": """Şemadan Kaçınma: Kaçınma biçiminde kişi, olumsuz duyguları veya hatırlatıcı durumları yaşamamak için duygusal, bilişsel ya da davranışsal olarak uzak durur. Bu durum kısa vadede rahatlama sağlasa da uzun vadede duygusal farkındalığı azaltabilir ve değişimi zorlaştırabilir."""
    }
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

# YENİ: ADMIN PANELİ GİRİŞİ
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))

    error = None
    if request.method == "POST":
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Hatalı Şifre!"

    return render_template_string("""
        <!doctype html>
        <title>Admin Girişi</title>
        <style>
            body { font-family: sans-serif; text-align: center; padding: 50px; background: #f4f7f6; }
            form { background: white; padding: 30px; border-radius: 8px; display: inline-block; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
            input { padding: 10px; width: 200px; border: 1px solid #ddd; border-radius: 4px; margin-bottom:10px; }
            button { padding: 10px 20px; background: #1e88e5; color: white; border: none; border-radius: 4px; cursor: pointer; }
            .error { color: red; margin-bottom: 10px; }
        </style>
        <form method="post">
            <h2 style="color:#333;">Yönetici Girişi</h2>
            {% if error %}<p class="error">{{ error }}</p>{% endif %}
            <input type="password" name="password" placeholder="Şifre" required><br>
            <button type="submit">Giriş Yap</button>
        </form>
    """, error=error)

# YENİ: ADMIN PANELİ DASHBOARD
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    # Tüm verileri tarihe göre (en yeni en üstte) çek
    results = TestResult.query.order_by(TestResult.timestamp.desc()).all()
    
    dashboard_html = """
    <!doctype html>
    <title>Admin Paneli</title>
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f4f7f6; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        .header { display: flex; justify-content: space-between; align-items: center; }
        .btn { padding: 10px 20px; background: #4CAF50; color: white; text-decoration: none; border-radius: 4px; font-weight: bold; }
        .btn:hover { background: #388E3C; }
        .logout { color: #d32f2f; text-decoration: none; font-size:0.9em; }
        
        table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 0.85em; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background-color: #1e88e5; color: white; position: sticky; top: 0; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        tr:hover { background-color: #f1f1f1; }
        .scroll-box { overflow-x: auto; }
    </style>
    <body>
        <div class="container">
            <div class="header">
                <div>
                    <h1>Katılımcı Verileri (Toplam: {{ count }})</h1>
                    <a href="/admin/logout" class="logout">Çıkış Yap</a>
                </div>
                <a href="/admin/export_csv" class="btn">📥 Tüm Verileri Excel (CSV) Olarak İndir</a>
            </div>
            
            <div class="scroll-box">
                <table>
                    <thead>
                        <tr>
                            <th>No</th>
                            <th>Tarih</th>
                            <th>Cinsiyet</th>
                            <th>Yaş</th>
                            <th>Medeni Durum</th>
                            <th>İlişki Süresi</th>
                            <th>Şemalar (Bölüm 1)</th>
                            <th>Başa Çıkma (Bölüm 2)</th>
                            <th>Çift Uyumu (Bölüm 3)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for r in results %}
                        <tr>
                            <td><b>{{ 1000 + r.id }}</b></td>
                            <td>{{ r.timestamp.strftime('%d.%m.%Y %H:%M') }}</td>
                            <td>{{ r.cinsiyet }}</td>
                            <td>{{ r.yas_araligi }}</td>
                            <td>{{ r.medeni_durum }}</td>
                            <td>{{ r.iliski_suresi }}</td>
                            <td>{{ r.triggered_stage1 }}</td>
                            <td>{{ r.triggered_stage2 }}</td>
                            <td>{{ r.triggered_stage3 }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    """
    return render_template_string(dashboard_html, results=results, count=len(results))

# YENİ: DETAYLI CSV İNDİRME (Güncellendi)
@app.route("/admin/export_csv")
def export_csv():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    results = TestResult.query.order_by(TestResult.id).all()
    
    # CSV Oluşturma
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Detaylı Başlık Satırı
    writer.writerow([
        'Katılımcı No', 'Tarih', 
        'Cinsiyet', 'Yaş Aralığı', 'Medeni Durum', 
        'Birlikte Yaşam', 'İlişki Tanımı', 'İlişki Süresi', 'Terapi Desteği',
        'Şemalar (Bölüm 1)', 'Başa Çıkma (Bölüm 2)', 'Çift Uyumu (Bölüm 3)', 
        'Ham Cevaplar (JSON)'
    ])
    
    # Veri Satırları
    for r in results:
        writer.writerow([
            1000 + r.id,
            r.timestamp.strftime('%Y-%m-%d %H:%M'),
            r.cinsiyet,
            r.yas_araligi,
            r.medeni_durum,
            r.birlikte_yasam,
            r.iliski_tanimi,
            r.iliski_suresi,
            r.terapi_destegi,
            r.triggered_stage1,
            r.triggered_stage2,
            r.triggered_stage3,
            r.all_answers_json
        ])
        
    output.seek(0)
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=tez_verileri_tam.csv"}
    )

# YENİ: ÇIKIŞ YAPMA
@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))


# --- MEVCUT ROTALAR (AYNEN DEVAM) ---

@app.route("/")
def index():
    info_page_html = """
    <!doctype html>
    <title>Bilgilendirme ve Onam</title>
    <style>
        {% raw %}
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; color: #333; text-align: center; }
        .container { max-width: 800px; margin: 0 auto; background-color: #fff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1); text-align: left; }
        h1 { color: #1e88e5; text-align: center; margin-bottom: 30px; }
        p { line-height: 1.8; margin-bottom: 20px; font-size: 1.05em; }
        .highlight { background-color: #eef8ff; padding: 15px; border-left: 5px solid #1e88e5; border-radius: 4px; margin: 20px 0; }
        .start-button { display: block; width: 100%; padding: 15px; background-color: #4CAF50; color: white; text-decoration: none; border: none; border-radius: 8px; font-size: 1.2em; cursor: pointer; transition: background-color 0.3s; margin-top: 40px; text-align: center; font-weight: bold; }
        .start-button:hover { background-color: #388E3C; }
        {% endraw %}
    </style>
    <body>
        <div class="container">
            <h1>Bilgilendirme ve Onam Formu</h1>
            
            <div class="highlight">
                <p><strong>Gizlilik Bildirimi:</strong> Yapacak olduğunuz bu test tamamen gizlidir. Kim olduğunuzu bilmemiz mümkün değildir ve bilgileriniz kişisel olarak kayıt altına alınmaz. Bu çalışma, bilimsel bir tez çalışmasına katkı sunmak için yapılmaktadır.</p>
            </div>

            <p>Soruları cevaplamaya devam ederek bu çalışmaya gönüllü olarak katıldığınızı ve katkı sağlamayı kabul ettiğinizi belirtmiş olursunuz.</p>

            <p>Bu test, hayatta olaylara ve insanlara bakış şeklimizi anlamaya yardımcı olur. <strong>Şema</strong> dediğimiz şey, yaşadıklarımız sonucunda kafamızda oluşan düşünme ve hissetme alışkanlıklarıdır. Hepimiz bunları fark etmeden çocukluktan beri geliştiririz. Bu şemalar çocuklukta karşılanmayan ihtiyaçlarımızdan dolayı oluşur.</p>

            <p>Bazen <em>“Neden hep aynı insan tipiyle karşılaşıyorum?”</em> deriz ya… İşte bunun sebebi tamamen bizim şemalarımızdan kaynaklanır. Bu yüzden şemalarınızı bilmek hayatınızdaki tüm ilişkilerde size yardımcı olacak ve kendinizi tanımanızı sağlayacaktır.</p>

            <p>Bu soruları doldurduğunuzda kendi şemalarınızı, bu şemalarla nasıl başa çıktığınızı ve ilişkilerinizde ne kadar mutlu ve memnun olduğunuzu daha iyi görebilirsiniz.</p>

            <p><strong>Soruların doğru ya da yanlış cevabı yoktur;</strong> önemli olan size en yakın olanı işaretlemenizdir. Tamamen samimi ve içten cevap verdiğinizde sonuçlar sizin için çok daha doğru ve faydalı olacaktır.</p>

            <p style="text-align: center; font-weight: bold; color: #d32f2f; margin-top: 30px;">
                TESTİN SONUNDA SONUÇLARINIZI ANINDA GÖREBİLECEKSİNİZ. <br> LÜTFEN TAM VE EKSİKSİZ DOLDURUNUZ.
            </p>

            <a href="/demographics" class="start-button">Okudum, Onaylıyorum ve Başlıyorum</a>
        </div>
    </body>
    """
    return render_template_string(info_page_html)


@app.route("/demographics")
def demographics_page():
    landing_page_html = """
    <!doctype html>
    <title>Demografik Bilgiler</title>
    <style>
        {% raw %}
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7f6; margin: 0; padding: 20px; color: #333; text-align: center; }
        .container { max-width: 700px; margin: 0 auto; background-color: #fff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1); text-align: left; }
        h1 { color: #1e88e5; text-align: center; margin-bottom: 20px; }
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
            <h1>Demografik Bilgiler</h1>
            <p>Lütfen teste başlamadan önce aşağıdaki bilgileri doldurun.</p>

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
    
    # 1. Aşamayı Başlat
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
    
    # Hangi soru setini kullanacağız?
    stage_key = f"stage{stage}"
    current_questions = QUESTIONS_DATA.get(stage_key, [])
    total_questions = len(current_questions)
    
    # Dinamik Başlıklar
    stage_titles = {
        1: "Bölüm 1: Young Şema Testi",
        2: "Bölüm 2: ŞEMA BAŞA ÇIKMA ÖLÇEĞİ",
        3: "Bölüm 3: YENİLENMİŞ ÇİFT UYUM ÖLÇEĞİ" 
    }
    current_title = stage_titles.get(stage, f"Bölüm {stage}")

    # POST İşlemi
    if request.method == "POST":
        action = request.form.get('action')
        qid = request.form.get('question_id')
        ans = request.form.get(f'q{qid}')
        
        # Geri gitme
        if action == 'previous':
            session['current_question_index'] = max(0, session['current_question_index'] - 1)
            return redirect(url_for('quiz'))

        # İleri gitme
        if ans:
            # Cevabı ilgili aşamanın sözlüğüne kaydet
            session[f'answers_stage{stage}'][qid] = int(ans)
            session.modified = True
            
            # İlerle
            session['current_question_index'] += 1
            return redirect(url_for('quiz'))

    # -- GET: Soru Gösterimi veya Geçiş Ekranı --
    
    # Eğer o aşamadaki sorular bittiyse:
    if index >= total_questions:
        if stage == 1:
            # 1 -> 2 Geçişi
            return render_template_string("""
                <div style="text-align:center; padding:50px; font-family:sans-serif;">
                    <h1 style="color:#1e88e5;">1. Bölüm Tamamlandı</h1>
                    <h2 style="color:#333; margin-top:20px;">2. Bölüm: ŞEMA BAŞA ÇIKMA ÖLÇEĞİ</h2>
                    <p style="font-size:1.1em; line-height:1.6; color:#555; max-width:700px; margin:20px auto;">
                        Aşağıda bireylere özgü bazı davranışları tanımlayan ifadeler yer almaktadır.
                        Lütfen her cümleyi dikkatli bir şekilde okuyup, her bir ifadenin sizi ne derece yansıttığını kendinize en uyan şekilde bir şık işaretleyin.
                    </p>
                    <a href="/start_stage_2" style="background:#4CAF50; color:white; padding:15px 30px; text-decoration:none; border-radius:5px; font-size:1.2em;">2. Bölüme Başla</a>
                </div>
            """)
        elif stage == 2:
            # 2 -> 3 Geçişi
            return render_template_string("""
                <div style="text-align:center; padding:50px; font-family:sans-serif;">
                    <h1 style="color:#1e88e5;">2. Bölüm Tamamlandı</h1>
                    <h2 style="color:#333; margin-top:20px;">3. Bölüm: YENİLENMİŞ ÇİFT UYUM ÖLÇEĞİ</h2>
                    <p style="font-size:1.1em; line-height:1.6; color:#555; max-width:700px; margin:20px auto;">
                        Bu ölçek evli ya da birlikte yaşayan çiftlerin ilişki kalitesini değerlendirmek amacıyla geliştirilmiştir.
                        Bu ölçeği cevapladıktan sonra ilişkinizdeki çift uyumunuz hakkında bir bilgi sahibi olacaksınız.
                        İki bölümden oluşmaktadır. Yönergelere dikkat ediniz. Kendinize en uyan şekilde bir şık işaretleyin.
                    </p>
                    <a href="/start_stage_3" style="background:#4CAF50; color:white; padding:15px 30px; text-decoration:none; border-radius:5px; font-size:1.2em;">3. Bölüme Başla</a>
                </div>
            """)
        else:
            # 3. Aşama da bitti -> Sonuçları Hesapla
            return redirect(url_for('submit'))

    if not current_questions:
        return f"HATA: {stage}. aşama soruları bulunamadı.", 500

    question = current_questions[index]
    
    # Daha önce verilmiş cevabı bul (Hatırlama Özelliği)
    current_answers_dict = session.get(f'answers_stage{stage}', {})
    existing_answer = current_answers_dict.get(str(question['id']))

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
        
        .btn-group { display: flex; gap: 10px; margin-top: 20px; }
        .btn-next { flex: 2; padding: 15px; background: #1e88e5; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 1.1em;}
        .btn-prev { flex: 1; padding: 15px; background: #757575; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 1.1em;}
        .btn-next:hover { background-color: #1565c0; }
        .btn-prev:hover { background-color: #616161; }
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
                
                {% if stage == 3 and index_display == 7 %}
                    <div style="background-color:#fff3cd; color:#856404; padding:10px; margin-bottom:15px; border:1px solid #ffeeba; border-radius:5px;">
                        <strong>Yönerge:</strong> Aşağıda eşinizle ve evliliğinizle ilgili bazı ifadeler yer almaktadır. Lütfen aşağıdaki ifadeleri okuyup size ne derece uygun olduğunu ilgili kutucuğu işaretleyiniz.
                    </div>
                {% endif %}

                <p style="font-size:1.2em; font-weight:bold;">{{ q.text }}</p>
                
                {% for opt in q.options %}
                <label>
                    <input type="radio" name="q{{ q.id }}" value="{{ opt.value }}" required {% if existing_answer == opt.value %}checked{% endif %}>
                    <span class="option-card">{{ opt.text }}</span>
                </label>
                {% endfor %}
                
                <div class="btn-group">
                    {% if index_display > 1 %}
                        <button type="submit" name="action" value="previous" class="btn-prev" formnovalidate>Önceki Soru</button>
                    {% endif %}
                    <button type="submit" name="action" value="next" class="btn-next">Sonraki Soru</button>
                </div>
            </form>
        </div>
    </body>
    """
    
    return render_template_string(question_html, q=question, title=current_title, stage=stage, index_display=index+1, total=total_questions, progress=progress_percent, existing_answer=existing_answer)


@app.route("/submit")
def submit():
    s1 = session.get('answers_stage1', {})
    s2 = session.get('answers_stage2', {})
    s3 = session.get('answers_stage3', {})
    demog = session.get('demographics', {})
    
    # Görünüm ve Veritabanı için listeler
    html_s1, html_s2, html_s3 = [], [], []
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

    # --- 1. VERİTABANINA KAYIT ---
    subject_no = 0 # Default
    try:
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
        
        # Kayıt sonrası ID'yi alıp 1000 ekle
        subject_no = 1000 + new_result.id
        
    except Exception as e:
        logging.error(f"Kayıt Hatası: {e}")

    # --- 2. E-POSTA RAPORU GÖNDER (YENİ) ---
    try:
        if subject_no > 0: # Sadece kayıt başarılıysa gönder
            send_report_via_brevo(demog, db_s1, db_s2, uyum_sonuc, subject_no)
    except Exception as e:
        logging.error(f"Rapor Gönderme Hatası: {e}")

    # --- 3. SONUÇ SAYFASI ---
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
            
            <div style="background:#e8f5e9; padding:15px; border-radius:8px; margin-bottom:20px; border:1px solid #c8e6c9; text-align:center;">
                <h3 style="margin:0; border:none; color:#2e7d32;">Teşekkürler!</h3>
                <p style="margin:5px 0 0 0;">Katılımcı Numaranız: <strong>{{ subject_no }}</strong></p>
            </div>

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
    
    return render_template_string(result_template, res1=html_s1, res2=html_s2, res3=html_s3, subject_no=subject_no)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
