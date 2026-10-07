# app/services/telegram_service.py
import requests
import time
import json
import os
import re
import threading
from app.services.encryption_service import encryption_service

class TelegramService:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.offset_file = os.path.join('data', 'telegram_offset.txt')
        self.raw_log_db_path = os.path.join('data', 'telegram_messages.json')
        self.ongoing_chats = {}

    def start(self):
        if self.running:
            print("LOG: Telegram Servisi zaten çalışıyor.")
            return

        settings = self.data_manager.get_settings()
        telegram_settings = settings.get('connections', {}).get('telegram', {})
        if not self._is_configured(telegram_settings):
            print("LOG: Telegram Servisi başlatılmadı (ayarlar eksik veya devre dışı).")
            return

        print("LOG: Telegram Servisi başlatılıyor...")
        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running or not self.thread:
            return
        print("LOG: Telegram Servisi durduruluyor...")
        self.running = False
        self.stop_event.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            print("UYARI: Telegram servis thread'i zamanında durmadı.")
        self.thread = None
        print("LOG: Telegram Servisi durduruldu.")

    def reload(self):
        print("LOG: Telegram Servisi yeniden yükleniyor...")
        self.stop()
        time.sleep(1)
        self.start()

    def _is_configured(self, telegram_settings):
        return telegram_settings.get('enabled') and telegram_settings.get('bot_token')

    def _send_message(self, api_url, chat_id, text):
        """Sends a message to a given chat_id via Telegram API."""
        send_message_url = f"{api_url}/sendMessage"
        payload = {'chat_id': chat_id, 'text': text}
        try:
            response = requests.post(send_message_url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"TELEGRAM MESAJ GÖNDERME HATASI: {e}")
            return None

    def find_order_update(self, order_info: str, user_name: str = None, user_email: str = None) -> str:
        """
        Searches for order information in the local Telegram message database.
        If user_name and user_email are provided, it performs a strict validation.
        Otherwise, it performs a search by order number only (e.g., for Telegram context).
        """
        telegram_settings = self.data_manager.get_settings().get('connections', {}).get('telegram', {})
        chat_id_to_check = telegram_settings.get('chat_id')
        if not chat_id_to_check:
            return "Telegram Chat ID'si ayarlanmamış."

        try:
            with open(self.raw_log_db_path, 'r', encoding='utf-8') as f:
                messages = json.load(f)
        except (IOError, json.JSONDecodeError):
            return "Telegram mesaj veritabanı bulunamadı veya boş."

        # Search for a message containing the exact order number
        for message in reversed(messages):
            if 'text' in message and str(message.get('chat', {}).get('id')) == str(chat_id_to_check):
                message_text = message['text']
                order_pattern = r'\b' + re.escape(order_info) + r'\b'

                if re.search(order_pattern, message_text, re.IGNORECASE):
                    # Found a message with the order number. Now validate user if details are provided.
                    if user_name and user_email:
                        name_match = re.search(r'isim\s*:\s*(.*)', message_text, re.IGNORECASE)
                        email_match = re.search(r'e-?\s*posta\s*:\s*(.*)', message_text, re.IGNORECASE)

                        extracted_name = name_match.group(1).strip() if name_match else ""
                        extracted_email = email_match.group(1).strip() if email_match else ""

                        if (extracted_name.lower() == user_name.lower() and
                            extracted_email.lower() == user_email.lower()):
                            return f"Siparişinizle ilgili son durum: '{message_text}'"
                        # If validation fails, continue searching for other potential matches.
                    else:
                        # No user details to validate, so return the first match.
                        return f"Siparişinizle ilgili son durum: '{message_text}'"

        # If the loop completes without finding a fully matching record
        return "Böyle bir sipariş yok, lütfen bilgilerinizi kontrol edin."


    def _get_offset(self):
        try:
            with open(self.offset_file, 'r') as f:
                return int(f.read().strip())
        except (IOError, ValueError):
            return 0

    def _save_offset(self, offset):
        with open(self.offset_file, 'w') as f:
            f.write(str(offset))

    def _archive_conversation(self, chat_id):
        if chat_id not in self.ongoing_chats: return

        chat_session = self.ongoing_chats.get(chat_id, {})
        conversation_history = chat_session.get('history', [])
        if not conversation_history: return

        # Determine chat type from the session, defaulting to 'kapat'
        chat_type = chat_session.get('type', 'kapat')

        if self.data_manager.archive_telegram_chat(conversation_history, chat_type):
            if chat_id in self.ongoing_chats:
                del self.ongoing_chats[chat_id]


    def _append_to_raw_log(self, new_messages):
        try:
            os.makedirs(os.path.dirname(self.raw_log_db_path), exist_ok=True)
            db_data = []
            if os.path.exists(self.raw_log_db_path):
                with open(self.raw_log_db_path, 'r', encoding='utf-8') as f:
                    db_data = json.load(f)

            existing_ids = {msg.get('message_id') for msg in db_data if 'message_id' in msg}
            unique_new_messages = [msg for msg in new_messages if msg.get('message_id') not in existing_ids]
            if not unique_new_messages: return

            db_data.extend(unique_new_messages)
            one_week_ago = time.time() - (7 * 24 * 60 * 60)
            filtered_data = [msg for msg in db_data if msg.get('date', 0) >= one_week_ago]

            with open(self.raw_log_db_path, 'w', encoding='utf-8') as f:
                json.dump(filtered_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"HATA: Telegram ham log dosyasına yazılamadı: {e}")

    def _fetch_and_process(self, api_url):
        last_offset = self._get_offset()
        get_updates_url = f"{api_url}/getUpdates"
        params = {'offset': last_offset + 1, 'limit': 100, 'timeout': 30}

        try:
            response = requests.get(get_updates_url, params=params, timeout=35)
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                print(f"TELEGRAM API HATASI: {data.get('description')}")
                if 'Unauthorized' in data.get('description', ''):
                    self.running = False
                return

            updates = data.get("result", [])
            if not updates: return

            messages = [update['message'] for update in updates if 'message' in update]
            if messages:
                self._append_to_raw_log(messages)
                for msg in messages:
                    chat_id = msg.get('chat', {}).get('id')
                    text = msg.get('text', '').strip()
                    if not chat_id: continue

                    # Initialize chat session if not present
                    if chat_id not in self.ongoing_chats:
                        self.ongoing_chats[chat_id] = {'history': [], 'state': None, 'type': None}

                    self.ongoing_chats[chat_id]['history'].append(msg)

                    current_state = self.ongoing_chats[chat_id].get('state')

                    # State-based logic
                    if current_state == 'awaiting_order_info':
                        order_info = text
                        status = self.find_order_update(order_info)
                        self._send_message(api_url, chat_id, status)

                        # Reset state after handling
                        self.ongoing_chats[chat_id]['state'] = None

                        # Follow-up message
                        self._send_message(api_url, chat_id, "Başka bir konuda yardımcı olabilir miyim? Lütfen sorunuzu yazın veya sohbeti sonlandırmak için /kapat yazın.")
                        continue # Move to the next message

                    # Keyword-based logic for starting flows
                    if "sipariş bilgisi" in text.lower():
                        self.ongoing_chats[chat_id]['state'] = 'awaiting_order_info'
                        self.ongoing_chats[chat_id]['type'] = 'Sipariş Bilgisi'

                        flow = self.data_manager.get_flow("order_info_flow")
                        if flow and flow.get('initial_prompt_responses'):
                            prompt = __import__('random').choice(flow['initial_prompt_responses'])
                            self._send_message(api_url, chat_id, prompt)
                        else:
                            self._send_message(api_url, chat_id, "Lütfen sipariş numaranızı girin.")
                        continue

                    elif "bilgi almak" in text.lower():
                        self.ongoing_chats[chat_id]['type'] = 'Bilgi Almak'
                        self._send_message(api_url, chat_id, "Elbette, size nasıl yardımcı olabilirim? Lütfen sorunuzu yazın.")
                        continue

                    elif "/kapat" in text.lower():
                        self._send_message(api_url, chat_id, "Görüşmek üzere!")
                        self._archive_conversation(chat_id)
                        continue

            self._save_offset(updates[-1]['update_id'])
        except requests.exceptions.RequestException as e:
            error_str = str(e)
            if "ConnectionResetError" in error_str or "409" in error_str:
                pass
            else:
                print(f"TELEGRAM AĞ HATASI: {e}")
        except Exception as e:
            print(f"TELEGRAM İŞLEME HATASI: {e}")

    def _run_loop(self):
        while self.running:
            try:
                settings = self.data_manager.get_settings()
                telegram_settings = settings.get('connections', {}).get('telegram', {})

                if not self._is_configured(telegram_settings):
                    print("LOG: Telegram Servisi devre dışı bırakıldı veya ayarlar eksik. 30 saniye sonra tekrar denenecek.")
                    self.stop_event.wait(30)
                    continue

                encrypted_token = telegram_settings.get('bot_token')

                if not encrypted_token:
                    print("LOG: Telegram token'ı ayarlanmamış. 30 saniye sonra tekrar denenecek.")
                    self.stop_event.wait(30)
                    continue

                bot_token = encryption_service.decrypt(encrypted_token)

                if not bot_token:
                    print("HATA: Telegram bot token'ı şifreli fakat çözülemedi. Lütfen ayarları kontrol edin. 30 saniye sonra tekrar denenecek.")
                    self.stop_event.wait(30)
                    continue

                api_url = f"https://api.telegram.org/bot{bot_token}"
                self._fetch_and_process(api_url)
                self.stop_event.wait(2)
            except Exception as e:
                print(f"HATA: Telegram dinleyici döngüsünde beklenmedik hata: {e}")
                self.stop_event.wait(60)
