import datetime
from functools import wraps
import jwt
from flask import current_app, g, jsonify, request
from app.services.security import user_stamp, permitted

def generate_token(email):
    from app import data_manager
    user=data_manager.get_user(email)
    if not user:
        raise ValueError('Kullanıcı bulunamadı.')
    now=datetime.datetime.now(datetime.timezone.utc)
    return jwt.encode({'sub':email, 'iat':now,
        'exp':now+datetime.timedelta(days=1, seconds=5),
        'ver':user_stamp(user), 'aud':'chatbot-panel'},
        current_app.config['JWT_SECRET_KEY'],algorithm='HS256')

def required_permission():
    name = (request.endpoint or '').split('.')[-1]
    groups = {
        'nav-chats': {'get_active_chats', 'get_chat_history'},
        'nav-archives': {'manage_archived_chats', 'get_archived_chat_by_id',
                         'get_prechat_submissions', 'delete_prechat_submissions', 'get_survey_submissions'},
        'nav-settings': {'get_prechat_settings', 'save_prechat_settings', 'get_theme_settings',
                         'save_theme_settings', 'get_canned_responses_settings',
                         'save_canned_responses_settings', 'get_survey_settings', 'save_survey_settings'},
        'nav-connections': {'get_connections_settings', 'save_email_connection_settings',
                            'save_telegram_connection_settings', 'test_email'},
        'nav-unanswered': {'answer_question', 'manage_unanswered', 'clear_all_unanswered'},
        'nav-answered': {'manage_answered', 'train', 'train_group'},
        'nav-library': {'manage_library', 'regroup_library_intents'},
        'nav-notifications': {'manage_notifications'},
        'nav-flows': {'get_flows', 'save_flow', 'delete_flow'},
        'nav-users': {'get_users', 'create_user', 'update_user', 'delete_user', 'get_group_users',
                      'add_user_to_group', 'delete_group_user', 'update_user_tags_route'},
        'nav-dashboard': {'dashboard_stats', 'get_bot_status'},
    }
    if name == 'set_bot_status':
        return 'nav-settings'
    if name == 'get_available_actions':
        return ('nav-library', 'nav-flows')
    return next((permission for permission, names in groups.items() if name in names), None)

def token_required(function):
    @wraps(function)
    def decorated(*args,**kwargs):
        from app import data_manager
        parts=request.headers.get('Authorization','').split()
        try:
            if len(parts)!=2 or parts[0]!='Bearer':
                raise jwt.InvalidTokenError()
            payload=jwt.decode(parts[1],current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256'],audience='chatbot-panel',
                options={'require':['sub','exp','iat','ver']})
            user=data_manager.get_user(payload['sub'])
            if not user or payload['ver']!=user_stamp(user):
                raise jwt.InvalidTokenError()
        except (jwt.InvalidTokenError,ValueError,TypeError,KeyError):
            return jsonify(message='Geçersiz veya süresi dolmuş token.'),401
        permission=required_permission()
        choices=permission if isinstance(permission,tuple) else (permission,)
        if not permission or not any(permitted(user,p) for p in choices):
            return jsonify(message='Bu işlem için yetkiniz yok.'),403
        g.api_user=user
        return function(user['email'],*args,**kwargs)
    return decorated
