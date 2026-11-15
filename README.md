# Chatbot — orijinal tasarım ve akışlar

Bu sürüm orijinal `chatbot2` dosyaları üzerinden yeniden hazırlanmıştır.
Ekranlar yeniden tasarlanmamış; CSS, mevcut Tailwind/Chart/Socket.IO yükleyicileri,
eventlet başlatıcısı, Bearer API akışı ve web üzerinden yönetici kaydı korunmuştur.

## Kurulum

1. Python 3.12 (64 bit) kurulu bir bilgisayarda bu klasörde `setup.bat` çalıştırın.
2. `start.bat` çalıştırın.
3. `http://127.0.0.1:5000/admin` adresini açın ve orijinal **Kayıt Ol** ekranından
   hesabınızı oluşturun. Yeni parolalarda en az 12 karakter kullanın; bcrypt için
   72 UTF-8 bayt sınırı vardır. Terminalden zorunlu yönetici hesabı açma adımı yoktur.

Her müşteri kendi yönetici hesabını alır ve kendi ekip üyelerini panelden ekler.
Diğer müşterilerin kullanıcıları, ayarları ve konuşmaları görünmez.
Paneldeki **Chatbot'a Git** bağlantısı müşterinin kendi sohbetini açar; bu bağlantının
`?group=...` bölümünü ziyaretçilerle paylaşırken koruyun. Mevcut `/`, `/admin`,
`/login`, `/signup`, API yolları ve Socket.IO olay adları korunmuştur.

Orijinal onaylanmış 27 niyet, 12 cevap bloğu, 2 akış ve gizli olmayan tema/form
ayarları `app/defaults.json` içinde başlangıç ayarıdır. Bunlar test konuşmaları
veya kullanıcı kayıtları değildir. Yeni hesaplar bu başlangıç ayarlarını alır;
sonraki düzenlemeler yalnızca o müşteriye aittir.

## Mevcut yerel kurulum

Mevcut kullanıcı ve konuşma verilerini korumak için önce orijinal klasörü yedekleyin.
Yeni klasöre yalnızca özel `data/` ve `.env` dosyalarınızı yerel olarak taşıyabilirsiniz;
eski bilgisayara bağlı `venv` klasörünü taşımayın. `setup.bat` yeni ortamı oluşturur.
`init_env.py` eksik/zayıf imzalama anahtarlarını yeniler; şifreli bağlantı ayarları için
gereken mevcut `ENCRYPTION_KEY` değerini değiştirmez. Eski oturumlarda yeniden giriş gerekir.

Veri dosyalarının adları ve konumları korunur. Müşteri ayrımı için dosyaların içine
grup alanı eklenir; eski biçimdeki veriler okunur ve mevcut ilk yönetici grubuna
bağlanır. Birden fazla eski yöneticiye ait ortak geçmişte sahiplik bilgisi yoksa
otomatik olarak kimlik tahmini yapılmaz. Orijinal klasörünüz bu çalışma tarafından
değiştirilmemiştir; geri dönüş için onu/yedeğinizi koruyun.

## Güvenlik nedeniyle görülen farklar

- Kayıtlı e-posta parolaları ve Telegram anahtarı tarayıcıya geri verilmez. Alanın
  kayıtlı olduğu belirtilir; boş kaydetmek önceki değeri korur.
- Menü izinleri sunucuda da uygulanır. Eski/silinmiş/yetkisi değişmiş kullanıcıların
  token ve oturumları geçersiz olur. Eski `admin` rolü de kendi müşteri grubuyla sınırlıdır.
- Kullanıcı metinleri HTML olarak çalıştırılmaz. CSRF kontrolleri görünmeyen alanlarla
  eklenmiştir; ekranların yerleşimi ve stilleri değişmez.
- Orijinal sayısal yazı boyutu (`14`), Türkçe font adları, TTF/OTF/WOFF/WOFF2 ve
  animasyonlu GIF yüklemesi korunur. Yüklemeler içerik/tür/boyut açısından denetlenir.
- Sipariş sorgusunun mevcut durum akışı korunur; yeni e-posta kodu adımı yoktur.
  Tam özel Telegram kaydı yerine yalnızca `Durum:` / `Status:` alanı döner.
  Sorgu tam sipariş numarasıyla yapılır; ad/e-posta gibi genel anahtar kelimelerle
  özel kayıt dökülmez. Bu, kimliği doğrulanmış özel sipariş portalı değildir;
  bu uçta yalnızca paylaşılabilir durum bilgisini tutun.
- Posta bağlantılarında TLS doğrulaması kullanılır. İç ağdaki posta sunucusu
  gerekiyorsa sunucu sahibi `.env` içinde `ALLOW_PRIVATE_MAIL_HOSTS` alanını ayarlar.

## GitHub ve yayınlama

Temiz ZIP'te `.env`, gerçek `data/`, kullanıcılar, konuşmalar, provider sırları,
testler, test verileri, raporlar, sanal ortam ve model önbelleği bulunmaz.
Üçüncü taraf paketler ve modeller ilk kurulumda/çalıştırmada indirilir.
Gerçek `.env` değerlerini `.env.example` dosyasına yazıp göndermeyin.

GitHub kodu saklar; bu Python uygulamasını GitHub Pages üzerinde çalıştıramazsınız.
İnternete açarken Python/Socket.IO destekli sunucu ve HTTPS kullanın;
`FLASK_DEBUG=False`, `COOKIE_SECURE=true` ayarlayın. Proxy, TLS ve sağlayıcı hesapları
gerçek dağıtım ortamında ayrıca doğrulanmalıdır. Dosya tabanlı veri katmanı tek
uygulama süreci içindir; çok süreçli dağıtım için ortak veri/mesaj katmanı gerekir.
Hiçbir yazılım için yüzde yüz saldırı güvenliği garantisi verilmez.
