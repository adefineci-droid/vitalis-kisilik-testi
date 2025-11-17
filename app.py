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
        "description": """Başarısızlık Şeması;Çocuklukta oluşumu:Sürekli kıyaslanan, yeterince takdir edilmeyen ya da başarıları küçümsenen çocuklarda gelişir. Aileden gelen “daha iyisini yapabilirdin” gibi mesajlar çocuğa sevgiyi ancak mükemmel olursa hak ettiği inancını kazandırır.<br>Yetişkinlikte:Bu şemaya sahip kişiler, içten içe “yeterince iyi değilim” düşüncesini taşırlar. İş ya da eğitim hayatında başarı elde etseler bile bunu hak ettiklerine inanmakta zorlanabilirler. Yeni bir göreve başlarken ya da önemli bir karar verirken başarısız olma korkusu belirgindir. “Ya beceremezsem, ya rezil olursam” düşünceleri onları risk almaktan uzaklaştırabilir. Bu kişiler genellikle potansiyellerinin altında performans sergilerler çünkü hata yapma ihtimali onları felç eder.<br>Bazıları mükemmeliyetçi bir çizgiye kayarak içlerindeki başarısızlık korkusunu örtmeye çalışır; sürekli çalışır, yorulur ama hiçbir zaman tatmin olmazlar. Derinlerde hep bir “bir gün herkes benim aslında o kadar da yetkin olmadığımı anlayacak” endişesi vardır."""
    },
    "Bağımlılık": {
        "question_ids": [6, 24, 60, 78],
        "threshold": 16,
        "description": """Bağımlılık Şeması:Çocuklukta oluşumu: Ebeveynlerin aşırı koruyucu, kontrolcü veya yönlendirici olduğu ailelerde görülür. Çocuk, karar alma ve deneme fırsatı bulamadığında kendi gücüne güvenmeyi öğrenemez. Ailede “sen tek başına yapamazsın, ben senin yerine hallederim” tutumu sıkça gözlemlenir.Yetişkinlikte:Bu şemaya sahip bireyler genellikle kendi kararlarını verirken tedirginlik yaşarlar. Bir işi kendi başına yapmak zorunda kaldıklarında içlerinde yoğun bir kaygı hissedebilirler. “Ya yanlış yaparsam?” düşüncesi onları sıklıkla durdurur. Çoğu zaman birine danışma, onay alma ya da destek görme ihtiyacı hissederler.İlişkilerinde aşırı bağlanma eğilimleri olabilir; partnerleri veya aileleri olmadan karar almakta zorlanırlar. Yalnız kalmak onlarda panik, kaygı ya da değersizlik duygusu yaratabilir. Dışarıdan güçlü görünseler bile içlerinde “tek başıma kalırsam kontrolü kaybederim” inancı vardır. Bu nedenle genellikle rehberlik veya yönlendirme arayışındadırlar."""
    },
    "Boyun Eğicilik": {
        "question_ids": [9, 27, 45, 63, 81],
        "threshold": 20,
        "description": """Boyun Eğicilik Şeması:Çocuklukta oluşumu:Otoriter, cezalandırıcı veya duygusal olarak tehditkâr aile ortamlarında gelişir. Çocuk, kendi düşüncelerini savunduğunda cezalandırılacağını ya da sevgiden mahrum kalacağını öğrenir. Kabul görmek için uyum sağlaması gerektiğini hisseder.Yetişkinlikte:Bu şemaya sahip kişiler genellikle çevrelerine aşırı uyum sağlar, kendi ihtiyaçlarını bastırır ve sürekli başkalarının beklentilerini öncelerler. “Hayır” demekte güçlük çekerler çünkü reddedilmekten veya çatışmadan korkarlar. İçlerinde sıklıkla şu düşünce vardır: “Kırılmaması için sessiz kalmalıyım.”Zamanla bastırılmış öfke ve kırgınlık birikir. Dışarıdan sakin, uyumlu veya anlayışlı görünseler de iç dünyalarında “kimse beni anlamıyor, hep ben veriyorum” serzenişi vardır. İlişkilerinde kendi sınırlarını koruyamadıkları için tükenmişlik, sessiz öfke veya kendini değersiz hissetme eğilimi sık görülür.Bu şemaya sahip bireyler genellikle başkalarının onayını korumaya çalışırken kendi benliklerini arka plana atarlar. Bu da uzun vadede duygusal mesafe, bastırılmış kimlik ve içsel yalnızlık hissi yaratır."""
    },
    "İç İçelik": {
        "question_ids": [8, 26, 44, 62, 80],
        "threshold": 20,
        "description": """İç İçelik (Gelişmemiş Benlik) Şeması:Çocuklukta oluşumu:Bu şema genellikle ebeveynle aşırı yakın ve duygusal bağımlılığın olduğu ailelerde gelişir. Çocuğun kendi tercihlerine ve duygularına alan tanınmaz; ebeveyn çoğu kararı onun yerine verir. “Ben senin için yaşıyorum” gibi ifadeler, çocuğun kendini ebeveynin devamı gibi görmesine neden olur.Yetişkinlikte:Bu şemaya sahip kişiler ilişkilerinde sıklıkla aşırı bağlılık ve duygusal bağımlılık geliştirirler. “Onsuz yaşayamam” veya “o olmayan bir hayat anlamsız” gibi düşünceler yoğundur. Partnerinin ya da aile üyesinin duygusal durumu, kendi duygusal halini belirleyebilir.Zaman zaman kendi istekleriyle yakınlarının isteklerini karıştırır; nerede bittiğini, karşısındakinin nerede başladığını ayırt etmekte zorlanır. Kendi yaşam kararlarını alırken “ya onu üzersen?” endişesi baskın hale gelebilir. İlişkiler kopmaya yöneldiğinde yoğun kaygı, boşluk ve yalnızlık duyguları yaşanabilir."""
    },
    "Terk Edilme": {
        "question_ids": [1, 19, 37, 55, 73],
        "threshold": 20,
        "description": """Terk Edilme Şeması:Çocuklukta oluşumu:Sık taşınmalar, ayrılıklar, boşanma ya da ebeveynin duygusal olarak erişilemez olduğu durumlar bu şemayı oluşturabilir. Çocuk, kendini sevilen ama her an kaybedilebilecek biri olarak algılar.Yetişkinlikte:Terk edilme şeması olan bireyler, yakın ilişkilerde yoğun kaybetme korkusu yaşarlar. Partnerleri bir süre sessiz kaldığında bile “beni artık istemiyor” kaygısı doğabilir. Küçük ilgisizlikleri büyük tehdit gibi algılarlar ve duygusal dalgalanmalar sıklıkla görülür.Bazıları terk edilmemek için fazlasıyla yapışkan, bazıları ise “nasıl olsa giderler” düşüncesiyle mesafeli ve soğuk davranabilir. İlişkilerinde gerçek yakınlık istedikleri halde, bu yakınlık onlarda kaygı yaratır. Sıklıkla “ya benim için burada kalmazsa?” düşüncesi eşlik eder."""
    },
    "Duygusal Yoksunluk": {
        "question_ids": [0, 18, 36, 54, 72],
        "threshold": 20,
        "description": """Duygusal Yoksunluk Şeması:Çocuklukta oluşumu:Sevgi, ilgi ya da empati gibi temel duygusal gereksinimlerin karşılanmadığı ortamlarda gelişir. Çocuk, isteklerine cevap alamadıkça duygusal ihtiyaçların önemsiz olduğuna inanabilir.Yetişkinlikte:Bu şemaya sahip kişiler genellikle “kimse beni gerçekten anlamıyor” duygusunu taşırlar. İlişkilerinde hep bir eksiklik hisseder, karşısındakinin sevgisini tam olarak hissedemezler. Partnerleri onları sevse bile, içten içe “benim duygularımı anlamıyor” diye düşünürler. Bu hissetme biçimi, çoğu zaman çocuklukta ihtiyaç duyulan şefkatin yokluğundan beslenir.Bazı kişiler bu boşlukla başa çıkmak için duygusal yakınlıktan tamamen kaçınabilir — soğuk ve mesafeli görünebilirler. Bazıları ise çok fazla bağlanarak içlerindeki açlığı doldurmaya çalışırlar. Her iki durumda da temel inanç şudur: “Kimse beni gerçekten anlamaz."""
    },
    "Sosyal İzolasyon": {
        "question_ids": [3, 39, 57, 75],
        "threshold": 16,
        "description": """Sosyal İzolasyon Şeması:Çocuklukta oluşumu:Aile içinde ya da okulda dışlanma, farklı hissettirilme ya da aidiyetin zayıf olduğu ortamlar bu şemayı besler. Çocuk kendini toplumdan ayrı ve anlaşılmamış hisseder.Yetişkinlikte:Bu şemaya sahip kişiler çoğu zaman “ben onlardan değilim” düşüncesini taşırlar. Sosyal ortamlarda güvensiz hissedebilir, kalabalıklar içinde bile yalnızlık yaşayabilirler. Diğerlerinin onları yargılayacağı veya reddedeceği korkusuyla kendilerini geri çekerler.Bazıları “ben zaten uymam” diye yakınlaşmaktan kaçınırken, bazıları katı bir uyum maskesi takabilir. İçlerinde sıklıkla ait olma arzusu vardır ama bu arzu “nasıl olsa anlamayacaklar” düşüncesiyle örtülüdür."""
    },
    "Duyguları Bastırma": {
        "question_ids": [11, 29, 47, 65, 83],
        "threshold": 20,
        "description": """Duyguları Bastırma Şeması:Çocuklukta oluşumu:Duyguların açıkça ifade edilmediği, duygusallığın zayıflık olarak görüldüğü ailelerde gelişir. Çocuk öfkesini, korkusunu veya sevgisini gösterdiğinde ayıplanmış ya da cezalandırılmış olabilir.Yetişkinlikte:Bu şemaya sahip kişiler duygularını göstermekten çekinirler. Ağlamayı, yardım istemeyi veya zayıf görünmeyi sevmeyebilirler. Dışarıdan soğukkanlı ve kontrollü görünseler de içlerinde yoğun duygusal gerilim taşırlar.İlişkilerinde duygusal yakınlıktan kaçınabilirler; çünkü duygularını açarlarsa “fazla hassas” ya da “güçsüz” görüneceklerinden korkarlar. Bazen öfke, üzüntü ya da sevgi yerine mantık ve kontrol ön plana çıkar. Zihinsel olarak yakın olsalar bile duygusal bağ kurmakta zorlanabilirler."""
    },
    "Kusurluluk": {
        "question_ids": [4, 22, 40, 58, 76, 42, 89],
        "threshold": 28,
        "description": """Kusurluluk Şeması:Çocuklukta oluşumu:Sürekli eleştirilen, reddedilen ya da başkalarıyla kıyaslanan çocuklarda gelişir. Çocuk, sevgiyi koşullu olarak alabileceğini öğrenir: “Hatalıysam sevilmem.”Yetişkinlikte:Kusurluluk şeması olan kişiler içten içe “bende bir yanlışlık var” duygusunu taşırlar. Başkalarının onları sevmesinin zor olduğunu düşünürler. İlişkilerde eleştiriye çok duyarlıdırlar; küçük bir yorum bile içlerinde büyük bir utanç yaratabilir. Bu kişiler genellikle kusurlarını gizlemeye, hatalarını örtmeye çalışır.Bir yandan da sürekli olarak onay ararlar — sevilmek, kabul edilmek ve “yeterli” olduklarını duymak isterler. Ancak içlerindeki ses “yine de eksiksin” der. Bu nedenle kimi zaman geri çekilme, kimi zaman da sürekli kendini kanıtlama davranışları görülür. Kendilerini başkalarıyla kıyaslama, değersiz hissetme ve beğenilmeye çalışma çabaları sıktır."""
    },
    "Büyüklenmecilik": {
        "question_ids": [21, 31, 49, 67, 85],
        "threshold": 20,
        "description": """Büyüklenmecilik Şeması:Çocuklukta oluşumu:Sınırların çizilmediği, çocuğun her isteğinin karşılandığı, kuralların belirsiz olduğu ailelerde gelişebilir. Bazen de tam tersi biçimde, değersiz hissettirilen çocuk “üstünlük duygusunu” bir savunma olarak geliştirebilir.Yetişkinlikte:Bu şemaya sahip kişiler genellikle kendilerini özel veya ayrıcalıklı hissederler. “Kurallar herkes için geçerli ama benim için değil.” düşüncesi baskındır. Kimi zaman başkalarının sınırlarına saygı göstermekte zorlanabilirler. Eleştiriye kapalıdırlar ve yanıldıklarını kabul etmekte güçlük çekerler.Yine de bu tutumun altında çoğu zaman derin bir görülme ve onaylanma ihtiyacı yatar. Başkalarından takdir almadıklarında değersizlik hissi yüzeye çıkar. Duygusal olarak savunmacı, bazen kibirli görünseler de aslında içlerinde kırılgan bir “beğenilme arzusu” taşırlar."""
    },
    "Statü Arayıcılık": {
        "question_ids": [12, 30, 13, 15, 33, 51, 69, 87],
        "threshold": 32,
        "description": """Statü Arayıcılık Şeması:Çocuklukta oluşumu:Ailenin başarı, mevki, statü ya da görünüşe fazla önem verdiği durumlarda gelişir. Çocuk, sevginin “başarıyla kazanılan” bir şey olduğuna inanır.Yetişkinlikte:Bu şemaya sahip kişiler değeri içsel özelliklerinden çok dışsal başarılarla ölçer. “Eğer başarılıysam, önemliyim.” düşüncesi baskındır. Hayatlarında sürekli bir yarış hissi vardır; daha fazla çalışır, daha fazla kazanır ama hiçbir zaman yeterli hissetmezler.Başarısız olduklarında veya takdir görmediklerinde yoğun değersizlik yaşarlar. Duygusal ilişkilerde de kendilerini statüyle tanımlarlar: partnerlerinin “gözünde yükselmek” onlar için önemlidir. Yorgun, tatminsiz ve sürekli hedef peşinde koşan bir ruh hali hâkimdir."""
    },
    "Yetersiz Özdenetim": {
        "question_ids": [14, 32, 50, 68, 86],
        "threshold": 20,
        "description": """Yetersiz Özdenetim Şeması:Çocuklukta oluşumu:Kuralların net olmadığı, çocuğa sınır koyulmayan ya da duygusal olarak aşırı serbest bırakılan ailelerde ortaya çıkar. Çocuk, dürtülerini düzenlemeyi ve sorumluluk almayı öğrenemez.Yetişkinlikte:Bu şemaya sahip bireyler genellikle anlık isteklerine göre hareket ederler. Sabırsız, ertesi günü düşünmeden karar veren ya da sık sık “dayanamayıp” sınırlarını aşan davranışlar gösterebilirler. Öz disiplin gerektiren durumlarda (örneğin düzenli çalışma, diyet, bir alışkanlığı bırakma) zorlanırlar.İçlerinde çoğu zaman “bunu şimdi istiyorum” duygusu baskındır. Bu kişiler için duygusal ya da fiziksel haz anı, uzun vadeli hedeflerin önüne geçer. Duygusal tepkileri de yoğun olabilir; öfke, hayal kırıklığı veya keyif duygusu hızla değişir."""
    },
    "Ekonomik Dayanıksızlık": {
        "question_ids": [61, 70],
        "threshold": 8,
        "description": """Ekonomik Dayanıksızlık Şeması:Çocuklukta oluşumu:Maddi belirsizliklerin, yoksunlukların veya güvensizliğin yaşandığı ailelerde görülür. Çocuk, güvenli bir ortamın ancak maddi istikrarla mümkün olduğuna inanır.Yetişkinlikte:Bu şemaya sahip bireyler, parasal konulara ilişkin sürekli bir “kaybetme” endişesi taşırlar. Mali durumu iyi olsa bile içlerinde “her an her şey bitebilir” korkusu vardır. Para biriktirme, tasarruf yapma ya da “kıtlık bilinciyle yaşama” eğilimleri görülür.Maddi güvenlik sağlanamadığında huzurları kaçar; güven duygusunu genellikle dışsal koşullara bağlarlar. Bu kişiler için “rahatlama” hissi, geleceğe dair kontrol duygusuyla birlikte gelir."""
    },
    "Kuşkuculuk": {
        "question_ids": [2, 20, 38, 56, 74, 43],
        "threshold": 24,
        "description": """Kuşkuculuk Şeması:Çocuklukta oluşumu:İhmal, aldatılma, cezalandırılma ya da sözel-fiziksel istismar deneyimleri sonucu gelişir. Çocuk, “insanlara güvenilmez” inancını öğrenir.Yetişkinlikte:Kuşkuculuk şeması olan kişiler, başkalarının niyetlerinden kolayca şüphe duyarlar. “Kesin bir çıkarı var” ya da “beni bir gün incitecek” düşünceleri akıllarının bir köşesindedir. Bu kişiler çoğu zaman güven duygusunu kontrol altında tutarak sağlarlar: mesafe koymak, sınır çizmek, her şeyi denetlemek gibi.İlişkilerinde tam bir teslimiyet veya yakınlık kurmak zor gelir. Çünkü zihinlerinde “çok yakınlaşırsam canım yanar” inancı vardır. Bu durum, samimiyet arzusu ile güven korkusu arasında bir gelgit yaratır."""
    },
    "Kendini Feda": {
        "question_ids": [10, 28, 46, 64, 82],
        "threshold": 20,
        "description": """Kendini Feda Şeması:Çocuklukta oluşumu:Ailenin ihtiyaçlarının ön planda olduğu, çocuğun kendi duygularını ifade edemediği ailelerde gelişir. Çocuk, sevgiyi “fedakârlık yaparak” kazandığını öğrenir.Yetişkinlikte:Bu şemaya sahip bireyler başkalarının mutluluğu için kendi isteklerinden vazgeçme eğilimindedirler. “Önce onlar iyi olsun” düşüncesiyle yaşarlar. Yardımsever, duyarlı ve fedakârdırlar ancak içten içe “benimle kim ilgilenecek?” sorusu yankılanır.Zamanla kendi ihtiyaçlarını bastırdıkları için yorgunluk, tükenmişlik ve kırgınlık hissederler. Duygusal olarak sevilmek ve görülmek isteseler de bunu dile getirmekte zorlanırlar. Sessiz bir beklentiyle, başkalarının fark etmesini umut ederler."""
    },
    "Cezalandırıcılık": {
        "question_ids": [48, 66, 84, 17, 35, 58, 71],
        "threshold": 28,
        "description": """Cezalandırıcılık ŞemasıÇocuklukta oluşumu:Hataların sert şekilde eleştirildiği veya cezalandırıldığı ortamlarda gelişir. Çocuk, kusursuz olmanın tek kabul edilme yolu olduğuna inanır.Yetişkinlikte:Bu şemaya sahip kişiler hata yapanlara karşı katı ve affetmez bir tutum sergileyebilir. Aynı sertliği kendilerine de gösterirler; bir hata yaptıklarında uzun süre kendilerini suçlar, pişmanlık hissederler. İçlerinde “yanlış yapan bedel ödemeli” inancı vardır.Bu kişiler genellikle vicdan sahibi ve yüksek sorumluluk duygusuna sahip olsalar da kendilerine karşı anlayışsızdırlar. Duygusal esneklikleri azdır; iç dünyalarında “ya hata yaparsam?” korkusu baskındır."""
    },
    "Dayanıksızlık/Karamsarlık": {
        "question_ids": [7, 25, 79, 16, 34, 52, 88],
        "threshold": 28,
        "description": """Dayanıksızlık / Karamsarlık Şeması:Çocuklukta oluşumu:Olumsuzlukların sık vurgulandığı, kaygılı veya tehditkâr aile ortamlarında gelişir. Çocuk, sürekli bir tehlike beklentisiyle büyür.Yetişkinlikte:Bu şemaya sahip kişiler, hayatın kötü yanlarına odaklanma eğilimindedir. Geleceğe dair umut duymakta zorlanırlar; “bir şey iyi gidiyorsa mutlaka bozulur” düşüncesi sıktır. Genellikle felaket senaryoları kurarlar, riskten kaçınırlar.Kaygı, endişe ve güvensizlik duyguları belirgindir. İyi giden olaylarda bile “bir yerde hata olmalı” düşüncesiyle rahatlayamazlar. Bu durum, kişiyi sürekli tetikte ve yorgun hale getirir."""
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
    explanations_html = [] # HTML listesi
    
    for name, rule in SCHEMA_RULES.items():
        total = sum([scores.get(str(qid), 0) for qid in rule["question_ids"]])
        if total >= rule["threshold"]:
            triggered.append(name)
            
            # YENİ: Her şema için tıklanabilir bir akordiyon kartı oluştur
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

    # YENİ: Akordiyon menüleri için güncellenmiş CSS stilleri
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
            
            <p style="text-align: center;"><a href="/">Yeniden Başla</a></p>
        </div>
    </body>
    """
    
    # Dinamik içerik oluşturuluyor
    result_content = ""
    if triggered:
        # YENİ: Başlığı ve kartları ayır
        result_content += '<h3 class="section-title">Tetiklenen Şemalar:</h3>'
        result_content += "".join(explanations_html)
    else:
        result_content += "<p>Tebrikler! Belirgin olarak tetiklenmiş bir şema tespit edilmedi.</p>"
    
    result_content += f'<p style="text-align:center; margin-top: 20px;">Toplam Cevaplanan Soru: {len(scores)}/{TOTAL_QUESTIONS}</p>'
    
    
    # template'i render_template_string ile işliyoruz
    return render_template_string(
        result_template,
        result_content=result_content
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
