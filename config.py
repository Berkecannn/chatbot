# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
    
    # E-posta Gönderme Ayarları (SMTP)
    SMTP_HOST = os.getenv('SMTP_HOST')
    SMTP_PORT = os.getenv('SMTP_PORT')
    SMTP_USER = os.getenv('SMTP_USER')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')

    # YENİ: E-posta Okuma Ayarları (IMAP)
    IMAP_HOST = os.getenv('IMAP_HOST')
    IMAP_USER = os.getenv('IMAP_USER')
    IMAP_PASSWORD = os.getenv('IMAP_PASSWORD')

    # Telegram Bot Ayarları
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

    SIMILARITY_THRESHOLD = 0.85
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')

    EMAIL_CONFIGURED = all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ADMIN_EMAIL])
    IMAP_CONFIGURED = all([IMAP_HOST, IMAP_USER, IMAP_PASSWORD])


    DEFAULT_SYSTEM_MESSAGES = {
        "welcome": "Merhaba! Size nasıl yardımcı olabilirim?",
        "fallback": "Bu soruyu anladığımdan emin değilim. Konuyu araştırıp size döneceğim.",
        "human_request_sending": "Müşteri temsilcisine bağlanma isteğiniz gönderiliyor...",
        "human_request_queued": "Talebiniz alınmıştır. Müşteri temsilcisine yönlendiriliyorsunuz, lütfen bekleyin.",
        "admin_connecting": "Bir operatöre bağlanıyorsunuz, lütfen bekleyin...",
        "admin_joined": "Bir operatör sohbete katıldı.",
        "admin_left": "Operatör sohbetten ayrıldı. Tekrar bota bağlandınız.",
        "admin_closed_chat": "Operatör sohbeti sonlandırdı. Yeni bir sohbet başlatmak için sayfayı yenileyebilirsiniz.",
        "order_info_request": "Lütfen sipariş numaranızı veya siparişinizle ilgili bir anahtar kelime girin.",
        "info_request_confirmation": "Elbette, size nasıl yardımcı olabilirim? Lütfen sorunuzu yazın.",
        "telegram_service_unavailable": "Üzgünüz, sipariş sorgulama servisi şu anda aktif değil.",
        "intent_process_error": "Üzgünüm, bu isteği işleyemedim.",
        "unknown_intent_response": "Bu konuda ne diyeceğimi bilemiyorum."
    }
