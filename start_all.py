# start_all.py
import eventlet
eventlet.monkey_patch()

from dotenv import load_dotenv
load_dotenv()

import atexit
from app import create_app

print("Uygulama ve servisler başlatılıyor...")

# Flask uygulamasını ve servis örneklerini oluştur
app, socketio = create_app()

# Servisleri app paketinden import et
from app import email_service, telegram_service

def stop_background_services():
    """Uygulama kapatıldığında arka plan servislerini düzgünce durdurur."""
    print("Uygulama kapatılıyor, arka plan servisleri durduruluyor...")
    if email_service:
        email_service.stop()
    if telegram_service:
        telegram_service.stop()

atexit.register(stop_background_services)

if __name__ == '__main__':
    # Arka plan servislerini başlat
    # Bu metodlar kendi thread'lerini kendileri yönetecek
    print("Arka plan servisleri başlatılıyor (eğer yapılandırıldıysa)...")
    if email_service:
        email_service.start()
    if telegram_service:
        telegram_service.start()

    print("\n" + "="*50)
    print("Uygulama çalışıyor!")
    print("Açmak için tarayıcınızda http://127.0.0.1:5000/ adresini ziyaret edin.")
    print("Admin Paneli: http://127.0.0.1:5000/admin")
    print("="*50 + "\n")

    # use_reloader=False ayarı, debug modunda script'in iki kez
    # çalışmasını ve dolayısıyla arka plan thread'inin iki kez başlatılmasını önler.
    socketio.run(
        app,
        host='127.0.0.1',
        port=5000,
        debug=app.config.get('DEBUG', False),
        use_reloader=False
    )