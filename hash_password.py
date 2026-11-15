import os
import bcrypt
from dotenv import load_dotenv

def hash_password():
    """
    .env dosyasından ADMIN_PASSWORD'u yükler, hash'ler ve hash'i yazdırır.
    """
    # .env dosyasından ortam değişkenlerini yükle
    load_dotenv()

    # Ortam değişkenlerinden yönetici şifresini al
    admin_password = os.getenv('ADMIN_PASSWORD')

    if not admin_password:
        print("Hata: ADMIN_PASSWORD, .env dosyasında bulunamadı.")
        print("Lütfen bu betiği çalıştırmadan önce .env dosyanızda ADMIN_PASSWORD'u ayarlayın.")
        return

    # Şifreyi hash'le
    hashed_password = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())

    # Hashlenmiş şifreyi yazdır
    print("\n--- Hashlenmiş Yönetici Şifresi ---")
    print(hashed_password.decode('utf-8'))
    print("\nYAPILMASI GEREKENLER:")
    print("1. Yukarıdaki hashlenmiş şifreyi kopyalayın.")
    print("2. Bu değeri .env dosyanızdaki 'ADMIN_HASHED_PASSWORD' değişkeni için ayarlayın.")
    print("3. Güvenlik için, hash'i ayarladıktan sonra düz metin 'ADMIN_PASSWORD'ü .env dosyanızdan kaldırmak isteyebilirsiniz.\n")

if __name__ == '__main__':
    hash_password()
