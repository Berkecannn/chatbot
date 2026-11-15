# app/services/telegram_service.py
import requests
import time
import json
import os
import re
import threading
import ssl
from app.services.encryption_service import encryption_service

class TelegramService:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self._workers = {}
        self.offset_file = os.path.join(data_manager.data_dir, 'telegram_offset.txt')
        self.raw_log_db_path = os.path.join(data_manager.data_dir, 'telegram_messages.json')
        self._customer_chats = {}

    def start(self):
        if self.running:
            print("LOG: Telegram Servisi zaten çalışıyor.")
            return

        configured = False
        for group in self.data_manager.get_group_ids():
            with self.data_manager.group_scope(group):
                settings = self.data_manager.get_settings().get('connections', {}).get('telegram', {})
                configured = configured or self._is_configured(settings)
        if not configured:
            return

        print("LOG: Telegram Servisi başlatılıyor...")
        self.running = True
        self.stop_event = threading.Event()
        self._workers = {}
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
        # Each poll reads current settings. Restarting the shared service here
        # could leave an old customer's polling thread alive after a timeout.
        if not self.running:
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
            print('Telegram bağlantı/işleme hatası; gizli ayrıntılar kayda yazılmadı.')
            return None

    def find_order_update(self, order_info: str, user_name: str = None, user_email: str = None) -> str:
        """Preserve order lookup; never return the full private Telegram record."""
        if not isinstance(order_info,str) or not 3<=len(order_info.strip())<=100:
            return 'Lütfen geçerli bir sipariş numarası girin.'
        configured = self.data_manager.get_settings().get('connections',{}).get('telegram',{}).get('chat_id')
        messages = self.data_manager._load_json(self.raw_log_db_path,[])
        for message in reversed(messages):
            if str(message.get('chat',{}).get('id')) != str(configured):
                continue
            text = message.get('text','')
            order = re.search(r'(?:sipari[şs]|order)\s*(?:no(?:su)?|numaras[ıi]|number|id)?\s*[:#-]\s*([A-Za-z0-9_-]+)',text,re.IGNORECASE)
            if not order or order.group(1).casefold()!=order_info.strip().casefold():
                continue
            if user_name and user_email:
                name = re.search(r'isim\s*:\s*([^\r\n]+)',text,re.IGNORECASE)
                email = re.search(r'e-?\s*posta\s*:\s*([^\r\n]+)',text,re.IGNORECASE)
                if not name or not email or name.group(1).strip().casefold()!=user_name.strip().casefold() or email.group(1).strip().casefold()!=user_email.strip().casefold():
                    continue
            status = re.search(r'(?:sipari[şs]\s+durumu|durum|status)\s*:\s*([^\r\n]+)',text,re.IGNORECASE)
            if status:
                value = status.group(1).strip()[:300]
                # Status is a public response field, not the customer record.
                # Do not inadvertently echo a contact address/phone in it.
                if re.search(r'[^\s@]+@[^\s@]+|(?:\+?\d[ ()-]*){10,}',value):
                    return 'Siparişinizin durum bilgisi alındı.'
                return "Siparişinizle ilgili son durum: '"+value+"'"
            return 'Sipariş kaydı bulundu; durum bilgisi henüz girilmemiş.'
        return 'Böyle bir sipariş yok, lütfen bilgilerinizi kontrol edin.'

    @property
    def ongoing_chats(self):
        return self._customer_chats.setdefault(self.data_manager.current_group(), {})

    def _get_offset(self):
        return int(self.data_manager._load_json(self.offset_file,0))

    def _save_offset(self, offset):
        self.data_manager._save_json(offset,self.offset_file)

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
            db_data = self.data_manager._load_json(self.raw_log_db_path,[])

            existing_ids = {msg.get('message_id') for msg in db_data if 'message_id' in msg}
            unique_new_messages = [msg for msg in new_messages if msg.get('message_id') not in existing_ids]
            if not unique_new_messages: return

            db_data.extend(unique_new_messages)
            one_week_ago = time.time() - (7 * 24 * 60 * 60)
            filtered_data = [msg for msg in db_data if msg.get('date', 0) >= one_week_ago]

            self.data_manager._save_json(filtered_data,self.raw_log_db_path)
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
                print('Telegram bağlantı/işleme hatası; gizli ayrıntılar kayda yazılmadı.')
        except Exception as e:
            print('Telegram bağlantı/işleme hatası; gizli ayrıntılar kayda yazılmadı.')

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
                stop.wait(2)

    def _process_group_once(self):
        settings = self.data_manager.get_settings().get('connections', {}).get('telegram', {})
        if not self._is_configured(settings):
            return
        token = encryption_service.decrypt(settings.get('bot_token',''))
        if token:
            self._fetch_and_process('https://api.telegram.org/bot'+token)

