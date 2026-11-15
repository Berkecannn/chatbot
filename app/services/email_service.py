# app/services/email_service.py
import imaplib
from .mail_security import SafeIMAP4_SSL
import email
import time
import re
import threading
import ssl
from email.header import decode_header
from .encryption_service import encryption_service

class EmailService:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self._workers = {}

    def start(self):
        if self.running:
            print("LOG: E-posta Okuma Servisi zaten çalışıyor.")
            return

        configured = False
        for group in self.data_manager.get_group_ids():
            with self.data_manager.group_scope(group):
                settings = self.data_manager.get_settings().get('connections', {}).get('email', {})
                configured = configured or self._is_imap_configured(settings)
        if not configured:
            return

        print("LOG: E-posta Okuma Servisi başlatılıyor...")
        self.running = True
        self.stop_event = threading.Event()
        self._workers = {}
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running or not self.thread:
            return
        print("LOG: E-posta Okuma Servisi durduruluyor...")
        self.running = False
        self.stop_event.set()
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            print("UYARI: E-posta okuma thread'i zamanında durmadı.")
        self.thread = None
        print("LOG: E-posta Okuma Servisi durduruldu.")

    def reload(self):
        # Each poll reads current settings. Restarting the shared service here
        # could leave an old customer's polling thread alive after a timeout.
        if not self.running:
            self.start()

    def _is_imap_configured(self, email_settings):
        required_keys = ['imap_host', 'imap_user', 'imap_password']
        return email_settings.get('enabled') and all(email_settings.get(key) for key in required_keys)

    def _run_loop(self):
        stop = self.stop_event
        while self.running and not stop.is_set():
            for group in self.data_manager.get_group_ids():
                worker = self._workers.get(group)
                if not worker or not worker.is_alive():
                    worker = threading.Thread(target=self._run_group, args=(group,stop), daemon=True)
                    self._workers[group] = worker
                    worker.start()
            stop.wait(2)

    def _run_group(self, group, stop):
        with self.data_manager.group_scope(group):
            while self.running and not stop.is_set():
                try:
                    self._process_group_once()
                except Exception:
                    print('Bağlantı servisi işlemi başarısız; gizli ayrıntılar kayda yazılmadı.')
                stop.wait(15)

    def _process_group_once(self):
        settings = self.data_manager.get_settings().get('connections', {}).get('email', {})
        if not self._is_imap_configured(settings):
            return
        if self.data_manager.get_unanswered_questions():
            self.check_for_replies(settings)

    def _extract_reply_text(self, body):
        body = body.replace('\r\n', '\n').strip()
        cut_off_point = len(body)
        separators = [
            re.compile(r'^\s*-----Original Message-----', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*----- Orijinal Mesaj -----', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*From\s*:', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*Gönderen\s*:', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*On .* wrote\s*:', re.MULTILINE | re.IGNORECASE),
            re.compile(r'^\s*\d{1,2}\s.*tarihinde.*yazd\u0131\s*:', re.MULTILINE | re.IGNORECASE)
        ]
        for sep_regex in separators:
            match = sep_regex.search(body)
            if match and match.start() < cut_off_point:
                cut_off_point = match.start()
        body = body[:cut_off_point]
        lines = body.strip().split('\n')
        cleaned_lines = [line for line in lines if not line.strip().startswith(('>', '|')) and not re.match(r'^\s*Sent from my .+', line.strip(), re.IGNORECASE)]
        body = '\n'.join(cleaned_lines).strip().split('\n--')[0].strip()
        return body

    def check_for_replies(self, imap_settings):
        try:
            host = imap_settings.get('imap_host')
            user = imap_settings.get('imap_user')
            encrypted_pass = imap_settings.get('imap_password')

            if not encrypted_pass:
                # This case should ideally not be reached if _is_imap_configured is working,
                # but as a safeguard, we log it calmly.
                print("LOG: IMAP şifresi ayarlanmamış.")
                return

            decrypted_password = encryption_service.decrypt(encrypted_pass)
            if not decrypted_password:
                print("HATA: IMAP şifresi şifreli fakat çözülemedi. Lütfen ayarları kontrol edin.")
                return

            with SafeIMAP4_SSL(host, ssl_context=ssl.create_default_context(), timeout=15) as mail:
                mail.login(user, decrypted_password)
                mail.select('inbox')

                search_query = '(SUBJECT "Yeni Chatbot Sorusu")'
                status, messages = mail.search(None, search_query)

                if status != 'OK' or not messages[0]:
                    return

                for num in messages[0].split():
                    if not self.running: break # Check if stop was called

                    status, data = mail.fetch(num, '(RFC822)')
                    if status != 'OK': continue

                    msg = email.message_from_bytes(data[0][1])
                    if 'In-Reply-To' not in msg and 'References' not in msg: continue

                    subject, encoding = decode_header(msg['Subject'])[0]
                    if isinstance(subject, bytes): subject = subject.decode(encoding if encoding else 'utf-8')

                    match = re.search(r'\[Token: ([\w-]+)\]', subject)
                    if not match: continue

                    token = match.group(1)
                    original_question = self.data_manager.get_question_from_reply_token(token)
                    if not original_question:
                        mail.store(num, '+FLAGS', '\\Seen')
                        continue

                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == 'text/plain' and "attachment" not in str(part.get("Content-Disposition")):
                                try: body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8'); break
                                except (UnicodeDecodeError, AttributeError): continue
                    else:
                        try: body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')
                        except (UnicodeDecodeError, AttributeError): continue

                    if not body:
                        mail.store(num, '+FLAGS', '\\Seen')
                        continue

                    reply_text = self._extract_reply_text(body)
                    if reply_text:
                        if self.data_manager.save_new_answer(original_question, reply_text):
                            self.data_manager.add_answer_to_pending(answer=reply_text, reply_token=token)

                    mail.store(num, '+FLAGS', '\\Seen')

        except imaplib.IMAP4.error as e:
            print(f"HATA: IMAP bağlantı hatası: {e}")
        except Exception as e:
            print(f"HATA: E-posta işleme sırasında genel hata: {e}")
