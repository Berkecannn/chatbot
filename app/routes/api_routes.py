# app/routes/api_routes.py
from flask import Blueprint, jsonify, request, session, current_app
import bcrypt
from config import Config
import random
import math
import os
import copy
from werkzeug.utils import secure_filename

from app import data_manager, nlu_service, notification_service, chat_manager, realtime_service, email_service, telegram_service
from app.services.auth_service import generate_token, token_required
from app.services.encryption_service import encryption_service
from config import Config

api_bp = Blueprint('api', __name__)

from app.services import user_service

# User Management API Routes
@api_bp.route('/users', methods=['GET'])
@token_required
def get_users(current_user):
    admin_user_data = data_manager.get_user(current_user)
    if not admin_user_data or admin_user_data.get('role') != 'admin':
        return jsonify({"message": "Yetkiniz yok"}), 403

    users = user_service.get_all_users()
    return jsonify(users)

@api_bp.route('/users', methods=['POST'])
@token_required
def create_user(current_user):
    admin_user_data = data_manager.get_user(current_user)
    if not admin_user_data or admin_user_data.get('role') != 'admin':
        return jsonify({"message": "Yetkiniz yok"}), 403

    data = request.get_json()
    success, message = user_service.create_new_user(
        email=data.get('email'),
        password=data.get('password'),
        role=data.get('role', 'user')
    )

    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 400

@api_bp.route('/users/<user_id>', methods=['PUT'])
@token_required
def update_user(current_user, user_id):
    admin_user_data = data_manager.get_user(current_user)
    if not admin_user_data or admin_user_data.get('role') != 'admin':
        return jsonify({"message": "Yetkiniz yok"}), 403

    data = request.get_json()
    new_role = data.get('role')

    success, message = user_service.update_user_role(user_id, new_role)

    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 404 if "bulunamadı" in message else 400


# --- Group User Management ---

@api_bp.route('/group_users', methods=['GET'])
@token_required
def get_group_users(current_user):
    """Fetches users belonging to the current group admin's group."""
    admin_user = data_manager.get_user(current_user)
    if not admin_user or admin_user.get('role') not in ['group_admin', 'admin']:
        return jsonify({"message": "Bu işlem için yetkiniz yok."}), 403

    # If 'admin', show all users. If 'group_admin', show only their group.
    if admin_user.get('role') == 'admin':
        return jsonify(data_manager.users)

    group_id = admin_user.get('group_id')
    all_users = data_manager.users
    group_users = [u for u in all_users if u.get('group_id') == group_id]
    return jsonify(group_users)


@api_bp.route('/group_users', methods=['POST'])
@token_required
def add_user_to_group(current_user):
    """Adds a new user to the group admin's group."""
    admin_user = data_manager.get_user(current_user)
    if not admin_user or admin_user.get('role') != 'group_admin':
        return jsonify({"message": "Bu işlem için yetkiniz yok."}), 403

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    permissions = data.get('permissions', [])
    tags = data.get('tags', [])

    if not email or not password:
        return jsonify({"success": False, "message": "E-posta ve şifre gereklidir."}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    group_id = admin_user.get('group_id')

    success, message = data_manager.add_user_to_group(
        email=email,
        hashed_password=hashed_password,
        group_id=group_id,
        permissions=permissions,
        tags=tags
    )

    if success:
        new_user = data_manager.get_user(email)
        return jsonify({"success": True, "message": message, "user": new_user})
    else:
        return jsonify({"success": False, "message": message}), 400


@api_bp.route('/group_users/<user_id>', methods=['DELETE'])
@token_required
def delete_group_user(current_user, user_id):
    """Deletes a user from a group."""
    admin_user = data_manager.get_user(current_user)
    if not admin_user or admin_user.get('role') != 'group_admin':
        return jsonify({"message": "Bu işlem için yetkiniz yok."}), 403

    success, message = data_manager.delete_user_from_group(user_id, admin_user)

    if success:
        return jsonify({"success": True, "message": message})
    else:
        # Use 403 for permission errors, 404 for not found, 400 for others
        if "yetkiniz yok" in message:
            return jsonify({"success": False, "message": message}), 403
        if "bulunamadı" in message:
            return jsonify({"success": False, "message": message}), 404
        return jsonify({"success": False, "message": message}), 400


@api_bp.route('/group_users/<user_id>/tags', methods=['PUT'])
@token_required
def update_user_tags_route(current_user, user_id):
    """Updates the tags for a user in the group."""
    admin_user = data_manager.get_user(current_user)
    if not admin_user or admin_user.get('role') != 'group_admin':
        return jsonify({"message": "Bu işlem için yetkiniz yok."}), 403

    data = request.get_json()
    tags = data.get('tags', [])

    success, message_or_user = data_manager.update_user_tags(user_id, tags, admin_user)

    if success:
        return jsonify({"success": True, "message": "Etiketler güncellendi.", "user": message_or_user})
    else:
        if "yetkiniz yok" in message_or_user:
            return jsonify({"success": False, "message": message_or_user}), 403
        if "bulunamadı" in message_or_user:
            return jsonify({"success": False, "message": message_or_user}), 404
        return jsonify({"success": False, "message": message_or_user}), 400


@api_bp.route('/users/<user_id>', methods=['DELETE'])
@token_required
def delete_user(current_user, user_id):
    admin_user_data = data_manager.get_user(current_user)
    if not admin_user_data or admin_user_data.get('role') != 'admin':
        return jsonify({"message": "Yetkiniz yok"}), 403

    success, message = user_service.delete_user_by_id(user_id, admin_user_data.get('id'))

    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 404 if "bulunamadı" in message else 400


@api_bp.route('/active_chats', methods=['GET'])
@token_required
def get_active_chats(current_user):
    """Aktif sohbet oturumlarının listesini döndürür."""
    return jsonify(chat_manager.get_all_sessions())

@api_bp.route('/chat/<session_id>', methods=['GET'])
@token_required
def get_chat_history(current_user, session_id):
    """Belirli bir sohbetin mesaj geçmişini döndürür."""
    history = chat_manager.get_chat_history(session_id)
    if history is not None:
        return jsonify(history)
    return jsonify({"message": "Sohbet bulunamadı."}), 404

@api_bp.route('/archived_chats', methods=['GET', 'DELETE'])
@token_required
def manage_archived_chats(current_user):
    if request.method == 'DELETE':
        chat_ids = request.json.get('chat_ids', [])
        if not chat_ids:
            return jsonify({"success": False, "message": "Sohbet ID'leri eksik."}), 400

        deleted_count = data_manager.remove_archived_chats(chat_ids)
        return jsonify({"success": True, "deleted_count": deleted_count})

    # Existing GET logic
    """Arşivlenmiş sohbetlerin listesini döndürür."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', None, type=str)

    all_chats = data_manager.get_archived_chats(search_term=search)
    total_items = len(all_chats)
    total_pages = math.ceil(total_items / per_page) if per_page > 0 else 0
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = all_chats[start:end]

    return jsonify({
        'items': paginated_items,
        'total_pages': total_pages,
        'current_page': page
    })

@api_bp.route('/archived_chats/<chat_id>', methods=['GET'])
@token_required
def get_archived_chat_by_id(current_user, chat_id):
    """ID ile belirli bir arşivlenmiş sohbeti döndürür."""
    all_chats = data_manager.get_archived_chats()
    chat = next((c for c in all_chats if c.get('chat_display_id') == chat_id), None)

    if chat:
        return jsonify(chat)
    return jsonify({"message": "Arşivlenmiş sohbet bulunamadı."}), 404


@api_bp.route('/settings/prechat', methods=['GET'])
@token_required
def get_prechat_settings(current_user):
    settings = data_manager.get_settings()
    prechat_config = settings.get('pre_chat', {})

    # If 'questions' is missing or is an empty list, provide the defaults.
    # This ensures the admin panel has a base to work from.
    if not prechat_config.get('questions'):
        prechat_config['questions'] = [
            {"id": "name", "type": "name", "text": "İsminiz nedir?", "required": True},
            {"id": "email", "type": "email", "text": "E-postanız nedir?", "required": True}
        ]

    return jsonify(prechat_config)

@api_bp.route('/public/prechat_form', methods=['GET'])
def get_public_prechat_form():
    """Returns the public-facing pre-chat form definition."""
    settings = data_manager.get_settings()
    prechat_config = settings.get('pre_chat', {'enabled': False, 'questions': []})

    # If the feature is enabled but no questions are configured, provide defaults.
    if prechat_config.get('enabled') and not prechat_config.get('questions'):
        prechat_config['questions'] = [
            {"id": "name", "type": "name", "text": "İsminiz nedir?", "required": True},
            {"id": "email", "type": "email", "text": "E-postanız nedir?", "required": True}
        ]

    return jsonify(prechat_config)

@api_bp.route('/public/theme', methods=['GET'])
def get_public_theme_settings():
    settings = data_manager.get_settings()
    theme_settings = settings.get('theme', {})
    # Ensure a default icon path is provided if not set
    if 'bot_icon_path' not in theme_settings:
        theme_settings['bot_icon_path'] = 'default_bot_icon.png'
    return jsonify(theme_settings)

@api_bp.route('/settings/prechat', methods=['POST'])
@token_required
def save_prechat_settings(current_user):
    data = request.get_json()
    if data is None:
        return jsonify({"message": "Invalid data"}), 400

    settings = data_manager.get_settings()
    if 'pre_chat' not in settings:
        settings['pre_chat'] = {}

    # The new structure includes an 'enabled' flag and a list of 'questions'
    settings['pre_chat']['enabled'] = data.get('enabled', False)
    settings['pre_chat']['questions'] = data.get('questions', []) # Changed from 'fields'

    data_manager.save_settings(settings)

    return jsonify({"message": "Pre-chat settings saved successfully."})

@api_bp.route('/settings/theme', methods=['GET'])
@token_required
def get_theme_settings(current_user):
    settings = data_manager.get_settings()
    theme_settings = settings.get('theme', {})
    # Ensure a default icon path is provided if not set
    if 'bot_icon_path' not in theme_settings:
        theme_settings['bot_icon_path'] = 'default_bot_icon.png'
    return jsonify(theme_settings)

@api_bp.route('/settings/theme', methods=['POST'])
@token_required
def save_theme_settings(current_user):
    settings = data_manager.get_settings()
    if 'theme' not in settings:
        settings['theme'] = {}

    # Preserve the existing icon and font paths, in case they are not re-uploaded.
    existing_icon_path = settings['theme'].get('bot_icon_path')
    existing_font_path = settings['theme'].get('custom_font_path')
    existing_font_family = settings['theme'].get('custom_font_family')


    # Global settings
    settings['theme']['primary_color'] = request.form.get('primary_color', '#4F46E5')
    settings['theme']['font'] = request.form.get('font', 'Inter')
    settings['theme']['font_size'] = request.form.get('font_size', '14px')
    settings['theme']['bot_name'] = request.form.get('bot_name', 'Destek Chatbot')

    # Light Mode Colors
    settings['theme']['page_bg_color_light'] = request.form.get('page_bg_color_light', '#F3F4F6')
    settings['theme']['chat_bg_color_light'] = request.form.get('chat_bg_color_light', '#FFFFFF')
    settings['theme']['user_bubble_color_light'] = request.form.get('user_bubble_color_light', '#4F46E5')
    settings['theme']['user_text_color_light'] = request.form.get('user_text_color_light', '#FFFFFF')
    settings['theme']['bot_bubble_color_light'] = request.form.get('bot_bubble_color_light', '#E5E7EB')
    settings['theme']['bot_text_color_light'] = request.form.get('bot_text_color_light', '#1F2937')
    settings['theme']['input_bg_color_light'] = request.form.get('input_bg_color_light', '#FFFFFF')
    settings['theme']['input_text_color_light'] = request.form.get('input_text_color_light', '#1F2937')


    # Dark Mode Colors
    settings['theme']['page_bg_color_dark'] = request.form.get('page_bg_color_dark', '#111827')
    settings['theme']['chat_bg_color_dark'] = request.form.get('chat_bg_color_dark', '#1F2937')
    settings['theme']['user_bubble_color_dark'] = request.form.get('user_bubble_color_dark', '#4F46E5')
    settings['theme']['user_text_color_dark'] = request.form.get('user_text_color_dark', '#FFFFFF')
    settings['theme']['bot_bubble_color_dark'] = request.form.get('bot_bubble_color_dark', '#374151')
    settings['theme']['bot_text_color_dark'] = request.form.get('bot_text_color_dark', '#F9FAFB')
    settings['theme']['input_bg_color_dark'] = request.form.get('input_bg_color_dark', '#374151')
    settings['theme']['input_text_color_dark'] = request.form.get('input_text_color_dark', '#F9FAFB')

    # Handle file upload
    if 'bot_icon' in request.files:
        file = request.files['bot_icon']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(current_app.static_folder, 'custom')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            settings['theme']['bot_icon_path'] = f'custom/{filename}'
        elif existing_icon_path:
            settings['theme']['bot_icon_path'] = existing_icon_path

    # Handle custom font upload
    if 'custom_font' in request.files:
        file = request.files['custom_font']
        if file and file.filename != '':
            font_family_name = request.form.get('font_family_name', 'CustomFont')
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(current_app.static_folder, 'custom_fonts')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            settings['theme']['custom_font_path'] = f'custom_fonts/{filename}'
            settings['theme']['custom_font_family'] = font_family_name
        elif existing_font_path:
             settings['theme']['custom_font_path'] = existing_font_path
             settings['theme']['custom_font_family'] = existing_font_family


    # Allow updating the font family name without re-uploading the file
    elif 'font_family_name' in request.form:
        if 'custom_font_path' in settings['theme']:
             settings['theme']['custom_font_family'] = request.form.get('font_family_name')


    print(f"DEBUG: Saving theme settings: {settings['theme']}")
    data_manager.save_settings(settings)

    return jsonify({"message": "Tema ayarları başarıyla kaydedildi.", "new_settings": settings['theme']})

@api_bp.route('/settings/canned_responses', methods=['GET'])
@token_required
def get_canned_responses_settings(current_user):
    settings = data_manager.get_settings()
    saved_responses = settings.get('canned_responses', {})

    # Start with the system defaults from Config, then overwrite with any saved values
    full_responses = Config.DEFAULT_SYSTEM_MESSAGES.copy()
    full_responses.update(saved_responses)

    return jsonify(full_responses)

@api_bp.route('/settings/canned_responses', methods=['POST'])
@token_required
def save_canned_responses_settings(current_user):
    data = request.get_json()
    if data is None:
        return jsonify({"message": "Invalid data"}), 400

    settings = data_manager.get_settings()
    if 'canned_responses' not in settings:
        settings['canned_responses'] = {}

    # List of all possible fields in this settings group
    canned_fields = [
        'welcome', 'fallback', 'human_request_sending', 'human_request_queued',
        'admin_connecting', 'admin_joined', 'admin_left', 'admin_closed_chat',
        'get_id_from_chat', 'user_id_request',
        'intent_process_error', 'unknown_intent_response'
    ]

    for field in canned_fields:
        if field in data:
            settings['canned_responses'][field] = data[field]

    data_manager.save_settings(settings)

    return jsonify({"message": "Metin ayarları başarıyla kaydedildi."})

@api_bp.route('/settings/survey', methods=['GET'])
@token_required
def get_survey_settings(current_user):
    survey_definition = data_manager.get_survey_definition()
    return jsonify(survey_definition)

@api_bp.route('/settings/survey', methods=['POST'])
@token_required
def save_survey_settings(current_user):
    data = request.get_json()
    if data is None:
        return jsonify({"message": "Invalid data"}), 400

    # TODO: Add validation for survey structure
    data_manager.save_survey_definition(data)

    return jsonify({"message": "Anket ayarları başarıyla kaydedildi."})

@api_bp.route('/settings/connections', methods=['GET'])
@token_required
def get_connections_settings(current_user):
    settings = data_manager.get_settings()
    connections = copy.deepcopy(settings.get('connections', {}))

    # Ensure default keys exist for both sections
    connections.setdefault('email', {'enabled': False})
    connections.setdefault('telegram', {'enabled': False})

    # --- Email Settings Processing ---
    email_settings = connections['email']
    email_req_keys = ['smtp_host', 'smtp_user', 'smtp_password', 'imap_host', 'imap_user', 'imap_password']
    if email_settings.get('enabled') and not all(email_settings.get(key) for key in email_req_keys):
        email_settings['enabled'] = False

    if email_settings:
        email_settings['imap_password'] = encryption_service.decrypt(email_settings.get('imap_password', ''))
        email_settings['smtp_password'] = encryption_service.decrypt(email_settings.get('smtp_password', ''))

    # --- Telegram Settings Processing (with default merging) ---
    saved_telegram_settings = connections.get('telegram', {})

    # Start with system defaults and then overwrite with any saved values.
    # This ensures all fields have a value and handles data migration implicitly.
    full_telegram_settings = Config.DEFAULT_SYSTEM_MESSAGES.copy()
    full_telegram_settings.update(saved_telegram_settings)

    # Re-assign the merged settings back to the main object
    connections['telegram'] = full_telegram_settings

    # Now use the merged object for checks and decryption
    telegram_settings = connections['telegram']
    if telegram_settings.get('enabled') and not telegram_settings.get('bot_token'):
        telegram_settings['enabled'] = False

    if telegram_settings:
        telegram_settings['bot_token'] = encryption_service.decrypt(telegram_settings.get('bot_token', ''))

    return jsonify(connections)

@api_bp.route('/settings/connections/email', methods=['POST'])
@token_required
def save_email_connection_settings(current_user):
    data = request.get_json()
    if data is None: return jsonify({"message": "Invalid data"}), 400

    settings = data_manager.get_settings()
    if 'connections' not in settings: settings['connections'] = {}
    if 'email' not in settings['connections']: settings['connections']['email'] = {}
    email_settings = settings['connections']['email']

    is_enabled = data.get('enabled', False)

    # Preserve existing passwords if new ones aren't provided
    imap_password = data.get('imap_password') or encryption_service.decrypt(email_settings.get('imap_password',''))
    smtp_password = data.get('smtp_password') or encryption_service.decrypt(email_settings.get('smtp_password',''))

    # Validate: if enabled, all critical fields must be present.
    email_req_fields = [data.get('imap_host'), imap_password, data.get('imap_user'), data.get('smtp_host'), smtp_password, data.get('smtp_user')]
    if is_enabled and not all(email_req_fields):
        is_enabled = False # Force disable if validation fails

    email_settings['enabled'] = is_enabled
    email_settings['imap_host'] = data.get('imap_host', '')
    email_settings['imap_user'] = data.get('imap_user', '')
    email_settings['smtp_host'] = data.get('smtp_host', '')
    email_settings['smtp_port'] = data.get('smtp_port', 587)
    email_settings['smtp_user'] = data.get('smtp_user', '')
    email_settings['smtp_sender'] = data.get('smtp_sender', '')
    email_settings['notification_recipient'] = data.get('notification_recipient', '')

    # Encrypt and save passwords if they were provided
    if data.get('imap_password'):
        email_settings['imap_password'] = encryption_service.encrypt(data['imap_password'])
    if data.get('smtp_password'):
        email_settings['smtp_password'] = encryption_service.encrypt(data['smtp_password'])

    data_manager.save_settings(settings)
    email_service.reload()
    return jsonify({"success": True, "message": "E-posta ayarları kaydedildi."})

@api_bp.route('/settings/connections/telegram', methods=['POST'])
@token_required
def save_telegram_connection_settings(current_user):
    data = request.get_json()
    if data is None: return jsonify({"message": "Invalid data"}), 400

    settings = data_manager.get_settings()
    if 'connections' not in settings: settings['connections'] = {}
    if 'telegram' not in settings['connections']: settings['connections']['telegram'] = {}
    telegram_settings = settings['connections']['telegram']

    is_enabled = data.get('enabled', False)

    # Preserve existing token if a new one isn't provided
    bot_token = data.get('bot_token') or encryption_service.decrypt(telegram_settings.get('bot_token', ''))

    # Validate: if enabled, token and chat_id must be present
    if is_enabled and not (bot_token and data.get('chat_id')):
        is_enabled = False # Force disable

    telegram_settings['enabled'] = is_enabled
    telegram_settings['chat_id'] = data.get('chat_id', '')

    # Save the new fields
    telegram_settings['initial_message'] = data.get('initial_message', '')
    telegram_settings['buttons'] = data.get('buttons', [])
    telegram_settings['order_info_request'] = data.get('order_info_request', '')
    telegram_settings['info_request_confirmation'] = data.get('info_request_confirmation', '')
    telegram_settings['telegram_service_unavailable'] = data.get('telegram_service_unavailable', '')


    if data.get('bot_token'):
        telegram_settings['bot_token'] = encryption_service.encrypt(data['bot_token'])

    data_manager.save_settings(settings)
    telegram_service.reload()
    return jsonify({"success": True, "message": "Telegram ayarları kaydedildi."})

@api_bp.route('/prechat/submit', methods=['POST'])
def submit_prechat():
    """Receives and saves pre-chat form submission data."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid data"}), 400

    if data_manager.save_prechat_submission(data):
        return jsonify({"success": True, "message": "Bilgileriniz için teşekkür ederiz!"})
    else:
        return jsonify({"success": False, "message": "Form kaydedilemedi."}), 500

@api_bp.route('/survey/submit', methods=['POST'])
def submit_survey():
    """Receives and saves survey submission data."""
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Invalid data"}), 400

    if data_manager.save_survey_result(data):
        return jsonify({"success": True, "message": "Anketiniz için teşekkür ederiz!"})
    else:
        return jsonify({"success": False, "message": "Anket kaydedilemedi."}), 500

@api_bp.route('/prechat_submissions', methods=['GET'])
@token_required
def get_prechat_submissions(current_user):
    """Returns paginated and searchable pre-chat submissions."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', None, type=str)

    all_submissions = data_manager.get_prechat_submissions(search_term=search)
    total_items = len(all_submissions)
    total_pages = math.ceil(total_items / per_page) if per_page > 0 else 0
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = all_submissions[start:end]

    return jsonify({
        'items': paginated_items,
        'total_pages': total_pages,
        'current_page': page
    })

@api_bp.route('/prechat_submissions', methods=['DELETE'])
@token_required
def delete_prechat_submissions(current_user):
    """Deletes selected pre-chat submissions."""
    ids = request.json.get('submission_ids', [])
    if not ids:
        return jsonify({"success": False, "message": "Submission ID'leri eksik."}), 400

    deleted_count = data_manager.remove_prechat_submissions(ids)
    return jsonify({"success": True, "deleted_count": deleted_count})


@api_bp.route('/survey_submissions', methods=['GET', 'DELETE'])
@token_required
def get_survey_submissions(current_user):
    if request.method == 'DELETE':
        ids = request.json.get('submission_ids', [])
        if not ids:
            return jsonify({"success": False, "message": "Submission ID'leri eksik."}), 400
        deleted_count = data_manager.remove_survey_results(ids)
        return jsonify({"success": True, "deleted_count": deleted_count})

    # GET request
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', None, type=str)

    all_submissions = data_manager.get_survey_results(search_term=search)
    total_items = len(all_submissions)
    total_pages = math.ceil(total_items / per_page) if per_page > 0 else 0
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = all_submissions[start:end]

    return jsonify({
        'items': paginated_items,
        'total_pages': total_pages,
        'current_page': page
    })

@api_bp.route('/bot_status', methods=['GET'])
@token_required
def get_bot_status(current_user):
    """Bot'un mevcut aktif/pasif durumunu döndürür."""
    return jsonify({'is_active': realtime_service.get_bot_status()})

@api_bp.route('/bot_status', methods=['POST'])
@token_required
def set_bot_status(current_user):
    """Bot'un durumunu değiştirir (aktif/pasif)."""
    data = request.json
    is_active = data.get('is_active')

    if is_active is None or not isinstance(is_active, bool):
        return jsonify({"success": False, "message": "Geçersiz veri: 'is_active' alanı (boolean) gereklidir."}), 400

    new_status = realtime_service.set_bot_status(is_active)

    from app import socketio
    socketio.emit('bot_status_changed', {'is_active': new_status}, namespace='/')

    return jsonify({"success": True, "is_active": new_status})

# ... Kalan API rotaları aynı kalır ...
@api_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    # This login is for the root admin defined in the .env file
    if email == Config.ADMIN_EMAIL and bcrypt.checkpw(password.encode('utf-8'), Config.ADMIN_HASHED_PASSWORD.encode('utf-8')):
        token = generate_token(email)
        return jsonify({'token': token})

    # For other users, authentication is handled by the main_routes.py login
    # This endpoint could be enhanced to handle all users if needed.
    return jsonify({"message": "Geçersiz kimlik bilgileri veya bu giriş yöntemi için yetkiniz yok."}), 401

@api_bp.route('/dashboard-stats')
@token_required
def dashboard_stats(current_user):
    stats = {
        'library_count': len(data_manager.get_library()),
        'unanswered_count': len(data_manager.get_unanswered_questions()),
        'answered_count': len(data_manager.get_answered_questions())
    }
    return jsonify(stats)

@api_bp.route('/answer', methods=['POST'])
@token_required
def answer_question(current_user):
    data = request.json
    question = data.get('question')
    answer = data.get('answer')

    if not question or not answer:
        return jsonify({"success": False, "message": "Soru veya cevap eksik."}), 400

    if data_manager.save_new_answer(question, answer):
        # Find the associated token to make the pending answer delivery more reliable
        reply_token = data_manager.get_token_for_question(question)
        data_manager.add_answer_to_pending(answer=answer, question=question, reply_token=reply_token)

        # Consume the token after use so it cannot be answered again via email
        if reply_token:
            notification_service.send_panel_answered_notification(reply_token, question)
            data_manager.get_question_from_reply_token(reply_token) # This consumes the token
            data_manager.consume_thread_info(reply_token) # Also consume the thread_info

        return jsonify({"success": True, "message": "Cevap kaydedildi."})

    return jsonify({"success": False, "message": "Cevap kaydedilemedi."}), 500

@api_bp.route('/unanswered', methods=['GET', 'DELETE'])
@token_required
def manage_unanswered(current_user):
    if request.method == 'GET':
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', None, type=str)

        all_questions = data_manager.get_unanswered_questions(search_term=search)
        total_items = len(all_questions)
        total_pages = math.ceil(total_items / per_page) if per_page > 0 else 0
        start = (page - 1) * per_page
        end = start + per_page
        paginated_items = all_questions[start:end]

        return jsonify({
            'items': paginated_items,
            'total_pages': total_pages,
            'current_page': page
        })
    if request.method == 'DELETE':
        questions = request.json.get('questions', [])
        data_manager.remove_unanswered_questions(questions)
        return jsonify({"success": True})

@api_bp.route('/unanswered/all', methods=['DELETE'])
@token_required
def clear_all_unanswered(current_user):
    """Tüm cevaplanmamış soruları temizler."""
    deleted_count = data_manager.clear_unanswered_questions()
    return jsonify({"success": True, "deleted_count": deleted_count})

@api_bp.route('/answered', methods=['GET', 'DELETE'])
@token_required
def manage_answered(current_user):
    if request.method == 'GET':
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', None, type=str)

        all_questions = data_manager.get_answered_questions(search_term=search)
        total_items = len(all_questions)
        total_pages = math.ceil(total_items / per_page) if per_page > 0 else 0
        start = (page - 1) * per_page
        end = start + per_page
        paginated_items = all_questions[start:end]

        return jsonify({
            'items': paginated_items,
            'total_pages': total_pages,
            'current_page': page
        })
    if request.method == 'DELETE':
        ids = request.json.get('ids', [])
        data_manager.remove_answered_questions(ids)
        return jsonify({"success": True})

@api_bp.route('/train', methods=['POST'])
@token_required
def train(current_user):
    ids = request.json.get('ids', [])
    count = data_manager.train_from_answered(ids)
    if count > 0:
        nlu_service.update_library_vectors()
    return jsonify({"success": True, "message": f"{count} öge kütüphaneye eklendi."})

@api_bp.route('/train-group', methods=['POST'])
@token_required
def train_group(current_user):
    data = request.json
    ids = data.get('ids', [])
    response_block = data.get('response_block', {})

    if not ids or not response_block or not response_block.get('responses'):
        return jsonify({"success": False, "message": "Eksik bilgi: ID listesi ve cevap bloğu gereklidir."}), 400

    count = data_manager.train_group_from_answered(ids, response_block)
    if count > 0:
        nlu_service.update_library_vectors()

    return jsonify({"success": True, "message": f"{count} soru yeni gruba eklendi."})

@api_bp.route('/library', methods=['GET', 'POST', 'DELETE', 'PUT'])
@token_required
def manage_library(current_user):
    if request.method == 'GET':
        # Admin arayüzü için kütüphaneyi cevaplara göre gruplanmış olarak getir
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', None, type=str)

        all_items = list(data_manager.get_library_grouped_by_response(search_term=search).items())
        total_items = len(all_items)
        total_pages = math.ceil(total_items / per_page) if per_page > 0 else 0
        start = (page - 1) * per_page
        end = start + per_page
        paginated_items = all_items[start:end]

        return jsonify({
            'items': dict(paginated_items),
            'total_pages': total_pages,
            'current_page': page
        })

    if request.method == 'POST':
        data = request.json
        response_data = data.get('response_data')
        intents = data.get('intents')
        if response_data is None or intents is None:
            return jsonify({"success": False, "message": "Eksik bilgi: response_data ve intents gereklidir."}), 400

        response_id = data_manager.create_response_group(response_data, intents)
        nlu_service.update_library_vectors()
        return jsonify({"success": True, "message": "Grup oluşturuldu.", "response_id": response_id}), 201

    if request.method == 'DELETE':
        response_id = request.json.get('response_id')
        if not response_id:
            return jsonify({"success": False, "message": "Eksik bilgi: response_id gereklidir."}), 400

        deleted_count = data_manager.delete_response_group(response_id)
        if deleted_count > 0:
            nlu_service.update_library_vectors()
            return jsonify({"success": True, "message": "Grup silindi."})
        else:
            return jsonify({"success": False, "message": "Grup bulunamadı."}), 404

    elif request.method == 'PUT':
        data = request.json
        response_id = data.get('response_id')
        response_data = data.get('response_data')
        intents = data.get('intents') # New: get the list of intents

        if not response_id or response_data is None or intents is None:
            return jsonify({"success": False, "message": "Eksik bilgi: response_id, response_data ve intents gereklidir."}), 400

        if data_manager.update_response_group(response_id, response_data, intents):
            # Niyetler değişmiş olabileceğinden NLU vektörlerini güncelle
            nlu_service.update_library_vectors()
            return jsonify({"success": True})
        return jsonify({"message": "Güncellenemedi."}), 500

@api_bp.route('/library/regroup', methods=['POST'])
@token_required
def regroup_library_intents(current_user):
    data = request.json
    intent_keys = data.get('intent_keys', [])
    response_block = data.get('response_block', {})

    if not intent_keys or not response_block or not response_block.get('responses'):
        return jsonify({"success": False, "message": "Eksik bilgi: Niyet anahtarları ve cevap bloğu gereklidir."}), 400

    count = data_manager.regroup_intents(intent_keys, response_block)
    if count > 0:
        nlu_service.update_library_vectors()

    return jsonify({"success": True, "message": f"{count} niyet yeniden gruplandırıldı."})

from app.services.utils import normalize_text

@api_bp.route('/notifications', methods=['GET', 'DELETE'])
@token_required
def manage_notifications(current_user):
    if request.method == 'GET':
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', None, type=str)

        all_items = data_manager.get_notifications(search_term=search)

        # Get all current unanswered questions for checking
        unanswered_qs = data_manager.get_unanswered_questions()
        unanswered_set = set(unanswered_qs)

        # Get all answered questions to prevent marking answered ones as deleted
        answered_qs_list = data_manager.get_answered_questions()
        answered_set = {item['question'] for item in answered_qs_list}

        # Check notifications for deletion status
        for item in all_items:
            # Only check notifications that are for an unanswered question
            if item.get('type') == 'unanswered_question':
                question_text = item.get('question')
                # A notification for an unanswered question should be marked as "deleted"
                # only if the question is truly gone (not in unanswered AND not in answered)
                if question_text and question_text not in unanswered_set and question_text not in answered_set:
                    item['is_deleted'] = True

        total_items = len(all_items)
        total_pages = math.ceil(total_items / per_page) if per_page > 0 else 0
        start = (page - 1) * per_page
        end = start + per_page
        paginated_items = all_items[start:end]

        return jsonify({
            'items': paginated_items,
            'total_pages': total_pages,
            'current_page': page
        })
    if request.method == 'DELETE':
        ids = request.json.get('ids', [])
        data_manager.remove_notifications(ids)
        return jsonify({"success": True})

@api_bp.route('/flows', methods=['GET'])
@token_required
def get_flows(current_user):
    """Returns all flow definitions."""
    all_flows = data_manager.get_all_flows()
    return jsonify(all_flows)

@api_bp.route('/flows/<flow_id>', methods=['POST', 'PUT'])
@token_required
def save_flow(current_user, flow_id):
    """Creates or updates a flow."""
    flow_data = request.get_json()
    if not flow_data:
        return jsonify({"success": False, "message": "Eksik veri."}), 400

    data_manager.save_flow(flow_id, flow_data)
    return jsonify({"success": True, "message": "Akış başarıyla kaydedildi."})

@api_bp.route('/flows/<flow_id>', methods=['DELETE'])
@token_required
def delete_flow(current_user, flow_id):
    """Deletes a flow."""
    if data_manager.delete_flow(flow_id):
        return jsonify({"success": True, "message": "Akış başarıyla silindi."})
    else:
        return jsonify({"success": False, "message": "Akış bulunamadı."}), 404

@api_bp.route('/test-email', methods=['POST'])
@token_required
def test_email(current_user):
    """ Test e-postası göndermek için API ucu """
    success, message = notification_service.send_test_email()
    if success:
        return jsonify({'success': True, 'message': message})
    else:
        return jsonify({'success': False, 'message': message}), 500

@api_bp.route('/actions', methods=['GET'])
@token_required
def get_available_actions(current_user):
    """Returns a list of all available actions for the admin panel."""
    actions = []

    # 1. Statik, önceden tanımlanmış eylemler
    static_actions = {
        "telegram_order_lookup": "Telegram Sipariş Sorgulama"
    }
    for action_id, name in static_actions.items():
        actions.append({"id": action_id, "name": name})

    # 2. Dinamik olarak akışlardan (flows) oluşturulan eylemler
    all_flows = data_manager.get_all_flows()
    for flow_id, flow_data in all_flows.items():
        action_id = f"start_flow:{flow_id}"
        # Akışın kendi adını kullanarak kullanıcı dostu bir isim oluştur
        name = f"Akış Başlat: {flow_data.get('name', flow_id)}"
        actions.append({"id": action_id, "name": name})

    return jsonify(actions)
