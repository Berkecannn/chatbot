# app/services/chat_manager.py
from datetime import datetime
import uuid
import pytz

class ChatManager:
    """
    Aktif sohbet oturumlarını ve ilgili verileri yönetir.
    """
    def __init__(self, data_manager=None):
        # Oturumları SID (Socket.IO Session ID) ile sakla
        self.sessions = {}
        self.data_manager = data_manager
        self.daily_chat_counter = 0
        self.last_chat_date = ""

    def create_session(self, sid):
        """Yeni bir sohbet oturumu oluşturur."""
        if sid not in self.sessions:
            istanbul_tz = pytz.timezone('Europe/Istanbul')
            now = datetime.now(istanbul_tz)

            # Günlük sayaç mantığı
            today_str = now.strftime('%Y%m%d')
            if today_str != self.last_chat_date:
                self.last_chat_date = today_str
                self.daily_chat_counter = 0

            self.daily_chat_counter += 1

            # Görüntülenecek yeni sohbet ID'sini oluştur
            chat_display_id = f"{today_str}{self.daily_chat_counter:04d}"

            self.sessions[sid] = {
                'sid': sid,
                'user_id': str(uuid.uuid4()), # Dahili kullanım için benzersiz ID
                'chat_display_id': chat_display_id, # Arayüzde gösterilecek ID
                'user_name': 'kullanıcı', # Varsayılan kullanıcı adı
                'user_email': None, # Pre-chat sonrası kullanıcı e-postası
                'start_time': now.isoformat(),
                'history': [],
                'is_admin_joined': False,
                'admin_sids': set(), # Bu sohbete katılan adminlerin SID'leri
                'human_request_active': False, # Müşteri temsilcisi talebi durumu
                'name_set': False, # Kullanıcının ismini girip girmediğini kontrol eder
                'id_requested_from_chat': False # Chat üzerinden ID istenip istenmediğini kontrol eder
            }
            print(f"Oturum oluşturuldu: {sid}, Görünen ID: {chat_display_id}")
        return self.sessions[sid]

    def set_user_name(self, sid, name):
        """Kullanıcının adını ve adının ayarlandığı durumunu günceller."""
        session = self.get_session(sid)
        if session:
            # İsim boş veya sadece boşluk içeriyorsa, varsayılan değeri koru.
            if name and name.strip():
                session['user_name'] = name.strip()
            # İsim ne olursa olsun, bu aşama geçildiği için name_set'i True yap.
            session['name_set'] = True
            print(f"Oturum {sid} için kullanıcı adı ayarlandı: {session['user_name']}")
            return True
        return False

    def set_user_details(self, sid, name, email):
        """Kullanıcının adını ve e-postasını günceller."""
        session = self.get_session(sid)
        if session:
            if name and name.strip():
                session['user_name'] = name.strip()
            if email and email.strip():
                session['user_email'] = email.strip()
            session['name_set'] = True # Mark that user details have been provided
            print(f"Oturum {sid} için kullanıcı detayları ayarlandı: Ad = {session['user_name']}, E-posta = {session['user_email']}")
            return True
        return False

    def set_chat_type(self, sid, chat_type):
        """Sohbet türünü oturum verisine ekler."""
        session = self.get_session(sid)
        if session:
            session['chat_type'] = chat_type
            print(f"Oturum {sid} için sohbet türü ayarlandı: {chat_type}")
            return True
        return False

    def set_id_requested_from_chat(self, sid, status):
        """Sets the status of whether the user ID has been requested via chat."""
        session = self.get_session(sid)
        if session:
            session['id_requested_from_chat'] = status
            return True
        return False

    def update_user_id(self, sid, new_user_id):
        """Updates the user_id and user_name for a given session."""
        session = self.get_session(sid)
        if session:
            if new_user_id and new_user_id.strip():
                session['user_id'] = new_user_id.strip()
                session['user_name'] = new_user_id.strip()
                session['name_set'] = True
                print(f"Oturum {sid} için Kullanıcı ID güncellendi: {new_user_id.strip()}")
                return True
        return False

    def get_session(self, sid):
        """Mevcut bir oturumu SID ile döndürür."""
        return self.sessions.get(sid)

    def remove_session(self, sid, should_archive=True):
        """Bir oturumu sonlandırır ve arşive kaydeder."""
        if sid in self.sessions:
            if should_archive:
                session_data = self.sessions.get(sid)
                if self.data_manager and session_data:
                    # Make sure set is converted to list for JSON serialization
                    session_data['admin_sids'] = list(session_data.get('admin_sids', []))
                    self.data_manager.archive_chat(session_data)
                print(f"Oturum sonlandırıldı ve arşivlendi: {sid}")
            else:
                print(f"Hayalet oturum arhivlenmeden sonlandırıldı: {sid}")

            del self.sessions[sid]

    def get_all_sessions(self):
        """Tüm aktif oturumların bir listesini döndürür."""
        # Döndürülen veride set'i listeye çevir
        return [
            {**session, 'admin_sids': list(session['admin_sids'])}
            for sid, session in self.sessions.items()
        ]

    def add_message(self, sid, sender, text):
        """Bir oturumun sohbet geçmişine mesaj ekler."""
        session = self.get_session(sid)
        if session:
            istanbul_tz = pytz.timezone('Europe/Istanbul')
            message = {
                'sender': sender, # 'user' veya 'bot' veya 'admin'
                'text': text,
                'timestamp': datetime.now(istanbul_tz).isoformat()
            }
            session['history'].append(message)
            return message
        return None

    def set_human_request_status(self, sid, status: bool):
        """Bir oturumun müşteri temsilcisi talebi durumunu ayarlar."""
        session = self.get_session(sid)
        if session:
            session['human_request_active'] = status
            print(f"Oturum {sid} için temsilci talebi durumu: {status}")
            return True
        return False

    def join_admin_to_chat(self, admin_sid, target_user_sid):
        """Bir admini belirli bir kullanıcı sohbetine dahil eder."""
        session = self.get_session(target_user_sid)
        if session:
            session['is_admin_joined'] = True
            session['admin_sids'].add(admin_sid)
            # Admin katıldığında, aktif insan talebini kapat
            session['human_request_active'] = False
            print(f"Admin {admin_sid}, {target_user_sid} sohbetine katıldı.")
            return True
        return False

    def leave_admin_from_chat(self, admin_sid, target_user_sid):
        """Bir adminin sohbetten ayrılmasını sağlar."""
        session = self.get_session(target_user_sid)
        if session and admin_sid in session['admin_sids']:
            session['admin_sids'].remove(admin_sid)
            # Eğer hiç admin kalmadıysa, is_admin_joined'i False yapabiliriz.
            if not session['admin_sids']:
                session['is_admin_joined'] = False
            print(f"Admin {admin_sid}, {target_user_sid} sohbetinden ayrıldı.")
            return True
        return False

    def clear_all_sessions(self):
        """Tüm aktif sohbet oturumlarını temizler."""
        self.sessions = {}
        print("Tüm aktif sohbet oturumları temizlendi.")

    def get_chat_history(self, sid):
        """Bir oturumun sohbet geçmişini döndürür."""
        session = self.get_session(sid)
        return session['history'] if session else []

    def get_admin_sids_for_user(self, user_sid):
        """Belirli bir kullanıcı sohbetine katılmış tüm adminlerin SID'lerini döndürür."""
        session = self.get_session(user_sid)
        return session['admin_sids'] if session else set()

    def leave_all_admins_from_chat(self, user_sid):
        """Bir sohbetten tüm adminleri çıkarır ve botu tekrar aktif hale getirir."""
        session = self.get_session(user_sid)
        if session:
            session['is_admin_joined'] = False
            session['admin_sids'].clear()
            print(f"Tüm adminler {user_sid} sohbetinden ayrıldı. Bot tekrar devrede.")
            return True
        return False
