# app/__init__.py
from flask import Flask
from flask_socketio import SocketIO, join_room, leave_room
from config import Config
from datetime import datetime

# Global references for services and SocketIO
socketio = SocketIO(cors_allowed_origins="*")
data_manager = None
ml_models = None
notification_service = None
nlu_service = None
email_service = None
chat_manager = None
realtime_service = None
telegram_service = None # Add telegram_service
admin_sids = set()

def create_app(config_class=Config):
    """Flask application factory."""
    global socketio, data_manager, ml_models, notification_service, nlu_service, email_service, chat_manager, realtime_service, telegram_service, admin_sids
    
    app = Flask(__name__)
    app.config.from_object(config_class)

    if not all([app.config.get('SECRET_KEY'), app.config.get('JWT_SECRET_KEY')]):
        raise ValueError("KRİTİK HATA: FLASK_SECRET_KEY ve JWT_SECRET_KEY ortam değişkenleri olarak ayarlanmalıdır!")

    # Initialize SocketIO with the app
    socketio.init_app(app)

    # Initialize services and models
    from .services.data_manager import DataManager
    from .services.ml_models import MLModels
    from .services.nlu_service import NLU_Service
    from .services.notification import NotificationService
    from .services.email_service import EmailService
    from .services.chat_manager import ChatManager
    from .services.realtime_service import RealtimeService
    from .services.telegram_service import TelegramService
    
    print("Servisler başlatılıyor...")

    chat_manager = ChatManager()
    data_manager = DataManager(data_dir='data', socketio=socketio, chat_manager=chat_manager)
    chat_manager.data_manager = data_manager
    ml_models = MLModels()

    # Services that depend on DataManager
    notification_service = NotificationService(data_manager=data_manager)
    email_service = EmailService(data_manager=data_manager)
    telegram_service = TelegramService(data_manager=data_manager)

    nlu_service = NLU_Service(
        data_manager=data_manager,
        ml_models=ml_models,
        threshold=config_class.SIMILARITY_THRESHOLD
    )
    realtime_service = RealtimeService()
    
    print("Servisler başarıyla ilklendirildi.")

    # Login Manager Setup
    from .routes.main_routes import login_manager
    login_manager.init_app(app)

    # Register Blueprints
    from .routes.main_routes import main_bp
    from .routes.api_routes import api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    # Import services for use in handlers
    from app import chat_manager, nlu_service, data_manager, socketio, realtime_service

    def send_and_log_message(sid, sender, response_text, bubbles=[]):
        """
        Helper function to log a message, send it to the user,
        and also send it to any listening admins.
        """
        # Log the message to the chat history
        message = chat_manager.add_message(sid, sender, response_text)
        if not message:
            return

        # 1. Send to the user
        user_payload = {'sender': sender, 'response': response_text, 'bubbles': bubbles}
        socketio.emit('new_message', user_payload, room=sid)

        # 2. Send to any listening admins
        admin_sids = chat_manager.get_admin_sids_for_user(sid)
        if admin_sids:
            # Admin payload needs the user_sid to identify the chat window
            admin_payload = {**message, 'user_sid': sid}
            for admin_sid in admin_sids:
                socketio.emit('new_message', admin_payload, room=admin_sid)

    def trigger_survey_if_enabled(user_sid, trigger_type):
        """
        Checks survey settings and sends the 'show_survey' event if the
        specified trigger is enabled.
        """
        survey_def = data_manager.get_survey_definition()
        if survey_def.get('enabled') and survey_def.get(trigger_type, False):
            # Pass the user's session ID with the survey data
            survey_def['user_sid'] = user_sid
            socketio.emit('show_survey', survey_def, room=user_sid)
            print(f"Anket tetiklendi: {user_sid}, neden: {trigger_type}")
            return True
        return False

    @socketio.on('connect')
    def handle_connect():
        """
        Handles a new client connection.
        A session is created for all connections. If the client is an admin,
        they will identify themselves via 'admin_connect' event,
        at which point their temporary chat session will be removed.
        """
        from flask import request
        sid = request.sid
        chat_manager.create_session(sid)
        # Notify admins about the new potential chat session.
        socketio.emit('active_chats_updated', {'sessions': chat_manager.get_all_sessions()}, room='admins')

    @socketio.on('update_user_details')
    def handle_update_user_details(data):
        """Updates the user details (name, email) for a session after pre-chat."""
        from flask import request
        sid = request.sid
        name = data.get('name')
        email = data.get('email')
        if chat_manager.set_user_details(sid, name, email):
            # Notify admins that the user's display name has changed
            socketio.emit('active_chats_updated', {'sessions': chat_manager.get_all_sessions()}, room='admins')

    @socketio.on('admin_connect')
    def handle_admin_connect():
        """
        Handles the event when an admin client connects and identifies itself.
        """
        from flask import request
        sid = request.sid
        # Add admin to our set of admin SIDs and to the 'admins' room
        admin_sids.add(sid)
        join_room('admins')
        # The 'connect' handler already created a session for this SID.
        # We must remove it, as admins should not appear as chat sessions.
        chat_manager.remove_session(sid, should_archive=False)
        print(f"Admin connected: {sid}. Joined 'admins' room and ghost session removed.")
        # Notify other admins to remove the admin's ghost session from their lists
        socketio.emit('active_chats_updated', {'sessions': chat_manager.get_all_sessions()}, room='admins')


    def _cleanup_unanswered_questions(user_sid):
        """
        Cleans up unanswered questions from a given user session by cross-referencing
        with the main unanswered questions list.
        """
        from .services.utils import normalize_text

        history = chat_manager.get_chat_history(user_sid)
        all_unanswered_qs = data_manager.get_unanswered_questions()

        if not history or not all_unanswered_qs:
            return

        normalized_unanswered_map = {normalize_text(q): q for q in all_unanswered_qs}

        session_user_messages = {msg['text'] for msg in history if msg.get('sender') == 'user'}

        questions_to_delete = []
        for user_msg in session_user_messages:
            normalized_msg = normalize_text(user_msg)
            if normalized_msg in normalized_unanswered_map:
                questions_to_delete.append(normalized_unanswered_map[normalized_msg])

        final_list_to_delete = list(set(questions_to_delete))

        if final_list_to_delete:
            data_manager.remove_unanswered_questions(final_list_to_delete)

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handles a client disconnection."""
        from flask import request
        sid = request.sid
        if sid in admin_sids:
            # If the disconnecting client was an admin, remove them from our records
            admin_sids.remove(sid)
            leave_room('admins')
            print(f"Admin disconnected: {sid}. Left 'admins' room.")
        else:
            # For a regular user, check if they had an active human request.
            session = chat_manager.get_session(sid)
            if session and session.get('human_request_active') and not session.get('is_admin_joined'):
                # The user disconnected before an admin could join the chat.
                # Mark the notification as 'closed' instead of deleting it.
                data_manager.update_human_request_notification_status(sid, "closed")
                print(f"User {sid} disconnected with an unhandled human request. Notification updated.")

            # Attempt to trigger the survey for inactivity/disconnect
            trigger_survey_if_enabled(sid, 'trigger_on_user_inactive')

            # Clean up their unanswered questions before removing the session
            _cleanup_unanswered_questions(sid)
            chat_manager.remove_session(sid)
            socketio.emit('active_chats_updated', {'sessions': chat_manager.get_all_sessions()}, room='admins')

    @socketio.on('start_chat')
    def handle_start_chat():
        """Sends the canned welcome message and session details."""
        from flask import request
        sid = request.sid
        session = chat_manager.get_session(sid)
        if not session:
            # This should ideally not happen if connect handler works
            session = chat_manager.create_session(sid)

        # Send session details (like the user-friendly chat ID) to the client
        socketio.emit('session_details', {'chat_display_id': session['chat_display_id']}, room=sid)

        # Load settings to get the dynamic welcome message
        settings = data_manager.get_settings()
        canned_responses = settings.get('canned_responses', {})
        welcome_message = canned_responses.get('welcome', Config.DEFAULT_SYSTEM_MESSAGES['welcome'])

        # Define the initial choice buttons conditionally
        telegram_settings = settings.get('connections', {}).get('telegram', {})
        initial_bubbles = []
        if telegram_settings.get('enabled'):
            initial_bubbles = [
                {"text": "Bilgi Almak", "value": "bilgi_almak"},
                {"text": "Sipariş Bilgisi", "value": "siparis_bilgisi"}
            ]

        send_and_log_message(sid, 'bot', welcome_message, bubbles=initial_bubbles)

    @socketio.on('user_message')
    def handle_user_message(data):
        """Handles messages from the user, directing them appropriately."""
        from flask import request
        sid = request.sid
        session = chat_manager.get_session(sid)
        user_text = data.get('msg', '').strip()
        message_value = data.get('value') # For button clicks

        settings = data_manager.get_settings()
        canned_responses = settings.get('canned_responses', {})
        pre_chat_settings = settings.get('pre_chat', {})

        # Check if we need to ask for User ID
        get_id_from_chat = canned_responses.get('get_id_from_chat', False)
        id_already_requested = session.get('id_requested_from_chat', False)
        pre_chat_disabled = not pre_chat_settings.get('enabled', False)
        user_id_is_default = session.get('user_name') == 'kullanıcı'


        if get_id_from_chat and pre_chat_disabled and user_id_is_default:
            if not id_already_requested:
                # First time, ask for the ID
                id_request_message = canned_responses.get('user_id_request', "Lütfen kullanıcı ID'nizi girin.")
                send_and_log_message(sid, 'bot', id_request_message)
                chat_manager.set_id_requested_from_chat(sid, True)
                return

            # If ID has been requested, this message is the ID
            new_user_id = user_text
            chat_manager.update_user_id(sid, new_user_id)

            # Now that we have the ID, send the welcome message
            welcome_message = canned_responses.get('welcome', Config.DEFAULT_SYSTEM_MESSAGES['welcome'])
            initial_bubbles = [
                {"text": "Bilgi Almak", "value": "bilgi_almak"},
                {"text": "Sipariş Bilgisi", "value": "siparis_bilgisi"}
            ]
            send_and_log_message(sid, 'bot', welcome_message, bubbles=initial_bubbles)
            # Mark as not needing ID anymore
            chat_manager.set_id_requested_from_chat(sid, False)
            return


        # Check for conversation state first
        current_state = session.get('state')
        if current_state:
            # This user is in a stateful flow.
            flow_id = session.get('flow_id')
            flow_definition = data_manager.get_flow(flow_id) if flow_id else None

            if flow_definition and flow_definition.get('state_to_set') == current_state:
                handler_def = flow_definition.get('reply_handler', {})
                handler_type = handler_def.get('type')

                if handler_type == 'telegram_order_lookup':
                    order_info = user_text
                    user_name = session.get('user_name')
                    user_email = session.get('user_email')

                    if not telegram_service:
                        send_and_log_message(sid, 'bot', canned_responses.get('telegram_service_unavailable', Config.DEFAULT_SYSTEM_MESSAGES['telegram_service_unavailable']))
                        del session['state']
                        del session['flow_id']
                        return

                    status = telegram_service.find_order_update(order_info, user_name, user_email)
                    send_and_log_message(sid, 'bot', status)

                    # If the lookup failed, keep the state to re-prompt the user.
                    if status == "Böyle bir sipariş yok, lütfen bilgilerinizi kontrol edin.":
                        return

                    # If lookup was successful, clear the state and show a follow-up menu.
                    del session['state']
                    del session['flow_id']
                    follow_up = handler_def.get('success_follow_up', {})
                    if follow_up.get('responses'):
                        response_text = __import__('random').choice(follow_up['responses'])
                        bubbles = follow_up.get('bubbles', [])
                        send_and_log_message(sid, 'bot', response_text, bubbles=bubbles)
                    return

                elif current_state == 'awaiting_user_query':
                    # This is the state for the general information flow.
                    # We clear the state here and let the message fall through to the NLU.
                    del session['state']
                    if 'flow_id' in session: del session['flow_id']

            # If we are in a state but can't find a handler, clear state and proceed.
            elif 'state' in session:
                del session['state']
                if 'flow_id' in session: del session['flow_id']

        # Durum: Bot aktif ve devrede. NLU ile cevap üret.
        intent = None
        if data.get('value'):
            intent = data.get('value')
        elif user_text:
            # Check for special keywords first
            if any(keyword in user_text.lower() for keyword in ["menü", "menüyü", "ne var"]):
                intent = "menu"
            else:
                # Fallback to NLU
                nlu_intent, score = nlu_service.get_intent(user_text)
                if nlu_intent:
                    intent = nlu_intent

        # --- Human Agent Request & Special Buttons ---
        is_human_request = data.get('request') == 'human_agent'
        if is_human_request:
            canned_responses = data_manager.get_settings().get('canned_responses', {})
            send_and_log_message(sid, 'system', canned_responses.get('human_request_sending', Config.DEFAULT_SYSTEM_MESSAGES['human_request_sending']))
            chat_manager.set_human_request_status(sid, True)
            user_name = session.get('user_name', sid[:5])
            notification_service.send_admin_notification(
                f"Kullanıcı ({user_name}) müşteri temsilcisi talebinde bulundu.",
                notification_type='human_request',
                sid=sid
            )
            send_and_log_message(sid, 'system', canned_responses.get('human_request_queued', Config.DEFAULT_SYSTEM_MESSAGES['human_request_queued']))
            socketio.emit('active_chats_updated', {'sessions': chat_manager.get_all_sessions()}, room='admins')
            return

        if intent == 'close_chat':
            send_and_log_message(sid, 'system', "Görüşmek üzere!")
            chat_manager.remove_session(sid)
            socketio.emit('chat_closed', {'user_sid': sid}, room=sid)
            return

        # --- Main Bot Logic ---
        message_content = user_text or data.get('value')
        if not message_content:
            return

        chat_manager.add_message(sid, 'user', message_content)

        is_bot_active = realtime_service.get_bot_status()
        is_admin_joined = session and session.get('is_admin_joined', False)

        if not is_bot_active or is_admin_joined:
            admin_sids = chat_manager.get_admin_sids_for_user(sid)
            if not admin_sids:
                socketio.emit('new_message_for_admin', {'user_sid': sid, 'message': message_content})
                if not is_admin_joined:
                    send_and_log_message(sid, 'system', canned_responses.get('admin_connecting', Config.DEFAULT_SYSTEM_MESSAGES['admin_connecting']))
            else:
                for admin_sid in admin_sids:
                    payload = {'user_sid': sid, 'sender': 'user', 'text': message_content, 'timestamp': datetime.utcnow().isoformat()}
                    socketio.emit('new_message', payload, room=admin_sid)
            return

        # --- Intent Processing ---
        if intent:
            response_data = data_manager.get_intent_data(intent)

            if response_data:
                action = response_data.get('action')

                # Case 1: Intent triggers a data-driven flow
                if action and action.startswith('start_flow:'):
                    flow_id = action.split(':', 1)[1]
                    flow_definition = data_manager.get_flow(flow_id)
                    if flow_definition:
                        session['flow_id'] = flow_id
                        session['state'] = flow_definition.get('state_to_set')
                        chat_manager.set_chat_type(sid, flow_definition.get('name', 'Flow'))

                        prompt_responses = flow_definition.get('initial_prompt_responses', [])
                        response_text = __import__('random').choice(prompt_responses) if prompt_responses else "Akış başlatılıyor..."
                        send_and_log_message(sid, 'bot', response_text)

                        socketio.emit('active_chats_updated', {'sessions': chat_manager.get_all_sessions()}, room='admins')
                        return
                    else:
                        # The action pointed to a flow that doesn't exist.
                        send_and_log_message(sid, 'bot', "Üzgünüm, bu işlem şu anda mevcut değil.")
                        return

                # Case 2: Standard intent with a simple text/bubble response
                else:
                    chat_manager.set_chat_type(sid, "Bilgi Almak")
                    responses = response_data.get("responses", [canned_responses.get('unknown_intent_response', Config.DEFAULT_SYSTEM_MESSAGES['unknown_intent_response'])])
                    response_text = __import__('random').choice(responses)
                    bubbles = response_data.get("bubbles", [])
                    send_and_log_message(sid, 'bot', response_text, bubbles=bubbles)
                    socketio.emit('active_chats_updated', {'sessions': chat_manager.get_all_sessions()}, room='admins')
                    return

            # Case 3: Intent was detected, but no response data found in library (orphaned intent)
            else:
                response_text = canned_responses.get('intent_process_error', Config.DEFAULT_SYSTEM_MESSAGES['intent_process_error'])
                send_and_log_message(sid, 'bot', response_text)
                return

        # --- Fallback: No Intent Detected ---
        response_text = canned_responses.get('fallback', Config.DEFAULT_SYSTEM_MESSAGES['fallback'])
        if data_manager.add_unanswered_question(user_text):
            reply_token = data_manager.create_reply_token(user_text)
            data_manager.add_pending_question(user_text, reply_token=reply_token, sid=sid)
            notification_service.send_admin_notification(
                f"Yeni soru: '{user_text[:70]}...'",
                reply_token=reply_token,
                question_text=user_text,
                sid=sid
            )

        send_and_log_message(sid, 'bot', response_text)
        trigger_survey_if_enabled(sid, 'trigger_on_bot_end')

    @socketio.on('admin_join_chat')
    def handle_admin_join_chat(data):
        """Adminin bir sohbete katılmasını sağlar."""
        from flask import request
        admin_sid = request.sid
        user_sid = data.get('user_sid')

        session = chat_manager.get_session(user_sid)
        if not session:
            socketio.emit('error', {'message': 'Oturum bulunamadı.'}, room=admin_sid)
            return

        # Operatör katılmadan ÖNCE mevcut durumu kontrol et
        was_admin_already_joined = session.get('is_admin_joined', False)
        had_human_request = session.get('human_request_active', False)

        if chat_manager.join_admin_to_chat(admin_sid, user_sid):
            # Eğer bu katılım bir "insan talebi" üzerine gerçekleştiyse, ilgili bildirimi temizle.
            if had_human_request:
                data_manager.remove_notifications_by_sid(user_sid)

            # Admine, sohbete başarıyla katıldığını bildir
            socketio.emit('admin_joined_successfully', {'user_sid': user_sid}, room=admin_sid)

            # Sadece ilk operatör katıldığında kullanıcıya bildirim gönder
            if not was_admin_already_joined:
                canned_responses = data_manager.get_settings().get('canned_responses', {})
                send_and_log_message(user_sid, 'system', canned_responses.get('admin_joined', Config.DEFAULT_SYSTEM_MESSAGES['admin_joined']))

            # Admin panellerini sohbetin durumu hakkında güncelle (yeni katılımı yansıtmak için)
            socketio.emit('active_chats_updated', {'sessions': chat_manager.get_all_sessions()}, room='admins')
        else:
            # Hata durumunda admine bilgi ver
            socketio.emit('error', {'message': 'Sohbete katılım başarısız.'}, room=admin_sid)

    @socketio.on('admin_message')
    def handle_admin_message(data):
        """Admin tarafından gönderilen mesajları işler."""
        from flask import request
        admin_sid = request.sid
        user_sid = data.get('user_sid')
        text = data.get('text')

        if not user_sid or not text:
            socketio.emit('error', {'message': 'Eksik bilgi: user_sid ve text gereklidir.'}, room=admin_sid)
            return

        message = chat_manager.add_message(user_sid, 'admin', text)

        if message:
            payload = {**message, 'user_sid': user_sid}
            # Mesajı kullanıcıya gönder
            socketio.emit('new_message', payload, room=user_sid)

            # Mesajı bu sohbete katılmış olan tüm adminlere gönder
            admin_sids = chat_manager.get_admin_sids_for_user(user_sid)
            for sid in admin_sids:
                socketio.emit('new_message', payload, room=sid)
        else:
            socketio.emit('error', {'message': 'Mesaj gönderilemedi.'}, room=admin_sid)

    @socketio.on('admin_leave_chat')
    def handle_admin_leave_chat(data):
        """
        Handles an admin's request to leave a chat and hand it back to the bot.
        """
        from flask import request
        admin_sid = request.sid
        user_sid = data.get('user_sid')

        if chat_manager.leave_all_admins_from_chat(user_sid):
            canned_responses = data_manager.get_settings().get('canned_responses', {})
            # Notify the.
            send_and_log_message(user_sid, 'system', canned_responses.get('admin_left', Config.DEFAULT_SYSTEM_MESSAGES['admin_left']))

            # Notify all admins to update their UI
            # The chat will now appear as 'Bekliyor' (Waiting) again
            socketio.emit('active_chats_updated', {'sessions': chat_manager.get_all_sessions()}, room='admins')

            # Also notify the specific admin that the action was successful
            # and close their chat window for this user
            socketio.emit('chat_closed', {'user_sid': user_sid}, room=admin_sid)
            print(f"Admin {admin_sid} left chat with {user_sid}. Handed back to bot.")
        else:
            socketio.emit('error', {'message': 'Sohbetten ayrılma başarısız oldu.'}, room=admin_sid)

    @socketio.on('admin_close_chat')
    def handle_admin_close_chat(data):
        """
        Handles an admin's request to completely terminate a chat session.
        """
        from flask import request
        admin_sid = request.sid
        user_sid = data.get('user_sid')

        session = chat_manager.get_session(user_sid)
        if session:
            # Clean up unanswered questions before removing the session
            _cleanup_unanswered_questions(user_sid)

            # Attempt to trigger the survey. If it's not triggered, send a default message.
            survey_triggered = trigger_survey_if_enabled(user_sid, 'trigger_on_admin_close')
            if not survey_triggered:
                canned_responses = data_manager.get_settings().get('canned_responses', {})
                send_and_log_message(user_sid, 'system', canned_responses.get('admin_closed_chat', Config.DEFAULT_SYSTEM_MESSAGES['admin_closed_chat']))

            # Remove the entire session from the manager
            chat_manager.remove_session(user_sid)

            # Notify all admins that this chat is now closed so they can update their UI.
            socketio.emit('chat_closed', {'user_sid': user_sid}, room='admins')
            print(f"Admin {admin_sid} closed chat with {user_sid}.")
        else:
            # This can happen if another admin already closed it.
            # Still, we want to ensure the requesting admin's window closes.
            socketio.emit('chat_closed', {'user_sid': user_sid}, room=admin_sid)
            print(f"Admin {admin_sid} tried to close an already closed chat with {user_sid}.")

    return app, socketio
