# app/services/notification.py
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from .encryption_service import encryption_service

class NotificationService:
    def __init__(self, data_manager):
        self.data_manager = data_manager

    def _send_email(self, msg, email_settings):
        """Genel e-posta gönderme fonksiyonu. Ayarları parametre olarak alır."""
        try:
            host = email_settings.get('smtp_host')
            port = email_settings.get('smtp_port')
            user = email_settings.get('smtp_user')
            encrypted_pass = email_settings.get('smtp_password')

            decrypted_password = encryption_service.decrypt(encrypted_pass)
            if not decrypted_password:
                error_message = "SMTP şifresi ayarlardan okundu ancak çözülemedi."
                print(f"KRİTİK HATA: {error_message}")
                return False, error_message

            if port == 465:
                with smtplib.SMTP_SSL(host, port) as server:
                    server.login(user, decrypted_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(host, port) as server:
                    server.starttls()
                    server.login(user, decrypted_password)
                    server.send_message(msg)

            return True, "E-posta başarıyla gönderildi."
        except smtplib.SMTPAuthenticationError as e:
            error_message = f"SMTP kimlik doğrulama hatası: {e}. Kullanıcı adı/şifre yanlış olabilir."
            print(f"KRİTİK HATA: {error_message}")
            return False, error_message
        except Exception as e:
            error_message = f"E-posta gönderilemedi: {e}"
            print(f"KRİTİK HATA: {error_message}")
            return False, error_message

    def _is_email_configured(self, email_settings):
        """Verilen e-posta ayarlarının geçerli olup olmadığını kontrol eder."""
        required_keys = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'notification_recipient']
        return email_settings.get('enabled') and all(email_settings.get(key) for key in required_keys)

    def send_admin_notification(self, message, notification_type='unanswered_question', reply_token=None, sid=None, question_text=None):
        """Yöneticilere bildirim gönderir."""
        display_id = None
        user_name = None
        if sid and hasattr(self.data_manager, 'chat_manager'):
            session = self.data_manager.chat_manager.get_session(sid)
            if session:
                display_id = session.get('chat_display_id')
                user_name = session.get('user_name')

        self.data_manager.add_notification(
            message, notification_type, sid=sid, question_text=question_text,
            user_name=user_name, chat_display_id=display_id
        )

        if notification_type == 'unanswered_question':
            settings = self.data_manager.get_settings()
            email_settings = settings.get('connections', {}).get('email', {})

            if not self._is_email_configured(email_settings):
                print("BİLDİRİM (E-posta Atlandı): E-posta ayarları tam olarak yapılandırılmamış veya devre dışı.")
                return

            final_display_id = display_id or reply_token
            final_user_name = user_name or "Bilinmiyor"
            message_id = make_msgid()
            self.data_manager.save_thread_info(reply_token, message_id, final_display_id)

            question_text = message.split("'")[1] if "'" in message else message
            subject = f"Yeni Chatbot Sorusu | Sohbet ID: {final_display_id} [Token: {reply_token}]"
            body = f"Merhaba Yönetici,\n\nChatbot'a yeni bir cevaplanmamış soru geldi:\n\nKullanıcı Adı: {final_user_name}\nSohbet ID: {final_display_id}\nSoru: \"{question_text}\"\n\nLütfen bu e-postayı doğrudan yanıtlayarak cevap verin. Cevabınız kullanıcıya iletilecektir.\n\n---\n"

            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Message-ID'] = message_id
            msg['Subject'] = subject
            msg['From'] = formataddr(('Chatbot', email_settings.get('smtp_user')))
            msg['To'] = email_settings.get('notification_recipient')
            msg['Reply-To'] = email_settings.get('smtp_user')

            success, result_message = self._send_email(msg, email_settings)
            if success:
                print(f"BİLDİRİM (E-posta Başarılı): {result_message}")
            else:
                self.data_manager.add_notification(f"Sistem Hatası: {result_message}", "system_error")

    def send_panel_answered_notification(self, reply_token, question_text):
        """Bir soru panelden cevaplandığında yöneticiye bilgilendirme e-postası gönderir."""
        settings = self.data_manager.get_settings()
        email_settings = settings.get('connections', {}).get('email', {})

        if not self._is_email_configured(email_settings):
            return

        thread_info = self.data_manager.get_thread_info(reply_token)
        if not thread_info or not thread_info.get('message_id'):
            return

        original_message_id = thread_info.get('message_id')
        display_id = thread_info.get('display_id', reply_token)
        subject = f"Re: Yeni Chatbot Sorusu | Sohbet ID: {display_id} [Token: {reply_token}]"
        body = f"Merhaba Yönetici,\n\nBu bildirim, aşağıdaki soruyla ilgilidir:\nSoru: \"{question_text}\"\n\nBu soru admin panelinden zaten cevaplanmıştır. Bu e-postaya yanıt vermenize gerek yoktur.\n\nBu e-posta, ilgili yazışmanın kapatılması için gönderilmiştir.\n\n---\n"

        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = formataddr(('Chatbot (Sistem)', email_settings.get('smtp_user')))
        msg['To'] = email_settings.get('notification_recipient')
        msg['In-Reply-To'] = original_message_id
        msg['References'] = original_message_id
        msg['Message-ID'] = make_msgid()

        self._send_email(msg, email_settings)

    def send_test_email(self):
        """Ayarlardaki yöneticiye bir test e-postası gönderir."""
        settings = self.data_manager.get_settings()
        email_settings = settings.get('connections', {}).get('email', {})

        if not self._is_email_configured(email_settings):
            return False, "E-posta ayarları yapılandırılmamış veya devre dışı."

        subject = "Chatbot Test E-postası"
        body = "Merhaba Yönetici,\n\nBu, chatbot uygulamanızdan gönderilen bir test e-postasıdır. Bu e-postayı aldıysanız, SMTP ayarlarınız doğru şekilde yapılandırılmıştır."

        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = formataddr(('Chatbot', email_settings.get('smtp_user')))
        msg['To'] = email_settings.get('notification_recipient')
        msg['Reply-To'] = email_settings.get('smtp_user')

        return self._send_email(msg, email_settings)
