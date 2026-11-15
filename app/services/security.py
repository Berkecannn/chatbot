"""Security checks shared by the original HTTP and Socket.IO entry points."""
import hashlib
import hmac
import json
import secrets
import threading
import time
from functools import wraps

from flask import abort, current_app, g, has_app_context, has_request_context, jsonify, request, session
from flask_login import current_user

socket_clients = {}
_limits = {}
_limit_lock = threading.RLock()
PERMISSIONS = {'nav-dashboard', 'nav-users', 'nav-unanswered', 'nav-answered',
    'nav-chats', 'nav-library', 'nav-notifications', 'nav-archives',
    'nav-settings', 'nav-connections', 'nav-flows'}

def manager():
    import app
    return app.data_manager

def user_stamp(user):
    values = {key: user.get(key) for key in ('password', 'role', 'group_id', 'permissions', 'auth_version')}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()

def current_principal():
    if not has_request_context() or not current_user.is_authenticated:
        return None
    user = manager().get_user(current_user.id)
    if not user or user.get('role') not in ('admin', 'group_admin', 'user'):
        return None
    stamp = getattr(current_user, 'auth_stamp', '')
    return user if hmac.compare_digest(stamp, user_stamp(user)) else None

def permitted(user, permission):
    return bool(user and user.get('role') in ('admin', 'group_admin', 'user') and
        (permission == 'nav-dashboard' or user['role'] in ('admin', 'group_admin') or
         permission in (user.get('permissions') or [])))

def allow(key, count, seconds=60):
    now = time.monotonic()
    with _limit_lock:
        if len(_limits) >= 10000:
            for entry in [k for k, (_, end) in _limits.items() if end <= now]:
                _limits.pop(entry, None)
            if key not in _limits and len(_limits) >= 10000:
                return False
        used, end = _limits.get(key, (0, now + seconds))
        if end <= now:
            used, end = 0, now + seconds
        _limits[key] = used + 1, end
        return used < count

def csrf_token():
    if not session.get('csrf_token'):
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']

def install(app):
    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def check_request():
        if request.content_length and request.content_length > app.config['MAX_CONTENT_LENGTH']:
            abort(413)
        ip = request.remote_addr or 'unknown'
        if request.path in ('/login', '/signup', '/api/login') and request.method == 'POST':
            if not allow(('login', ip), 20, 300):
                abort(429)
        if request.path.startswith('/api/') and not allow(('http', ip), 300):
            abort(429)
        mutating = request.method in ('POST', 'PUT', 'PATCH', 'DELETE') or request.path == '/logout'
        if mutating and not request.headers.get('Authorization', '').startswith('Bearer '):
            supplied = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token') or request.args.get('csrf_token', '')
            expected = session.get('csrf_token', '')
            if not expected or not hmac.compare_digest(str(supplied), str(expected)):
                abort(400, description='Güvenlik doğrulaması başarısız. Sayfayı yenileyin.')
        if request.is_json and request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                abort(400, description='JSON nesnesi gereklidir.')
        if request.endpoint == 'main.index':
            public_id = request.args.get('group')
            if public_id:
                group = manager().group_from_public_id(public_id)
                if not group:
                    abort(404)
            else:
                user = current_principal()
                group = user['group_id'] if user else manager()._default_group
            session['chat_group'] = group
            g.chat_group = group or '__public__'
        elif request.path.startswith('/api/public/') or request.path in ('/api/prechat/submit','/api/survey/submit'):
            group=session.get('chat_group')
            g.chat_group=group if group in manager().get_group_ids() else (manager()._default_group or '__public__')

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'same-origin'
        # Keep the original Tailwind runtime, inline theme styles and page scripts.
        response.headers['Content-Security-Policy'] = "object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if request.path.startswith(('/admin', '/login', '/api/')):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(413)
    @app.errorhandler(429)
    def safe_error(error):
        if request.path.startswith('/api/'):
            return jsonify(message=error.description), error.code
        return app.response_class(str(error.description), status=error.code, mimetype='text/plain')

def bind_socket(auth=None):
    user = current_principal()
    visitor = isinstance(auth, dict) and auth.get('client') == 'visitor'
    group = user['group_id'] if user and not visitor else session.get('chat_group')
    if group not in manager().get_group_ids():
        group = manager()._default_group or '__public__'
    g.chat_group = group
    socket_clients[request.sid] = {'group': group,
        'email': user['email'] if user and not visitor else None,
        'stamp': user_stamp(user) if user and not visitor else None}
    return group

def prune_sockets():
    import app
    for sid, saved in list(socket_clients.items()):
        if saved.get('revoked'):
            continue
        if not saved['email']:
            continue
        user = manager().get_user(saved['email'])
        if not user or user_stamp(user) != saved['stamp']:
            saved['revoked'] = True
            if has_app_context():
                with current_app.app_context():
                    app.socketio.server.disconnect(sid, namespace='/')
            else:
                app.socketio.server.disconnect(sid, namespace='/')

def emit_scoped(event, payload=None, **options):
    import app
    group = manager().current_group()
    prune_sockets()
    if options.get('room') == 'admins':
        options['room'] = 'admins:' + group
    if not options.get('room') and not options.get('to'):
        options['room'] = 'admins:' + group
    return app.socketio.emit(event, payload, **options)

def socket_check(admin=False, disconnecting=False):
    def decorate(function):
        @wraps(function)
        def checked(*args, **kwargs):
            from flask_socketio import emit
            saved = socket_clients.get(request.sid)
            if saved:
                g.chat_group = saved['group']
            if not disconnecting:
                if not allow(('socket', request.remote_addr or 'unknown'), 180):
                    emit('error', {'message': 'Çok fazla istek. Lütfen bekleyin.'})
                    return
                if args and not isinstance(args[0], dict):
                    emit('error', {'message': 'Geçersiz veri.'})
                    return
                if args:
                    for key, limit in {'msg':4000,'text':4000,'name':200,'email':254,'user_sid':100,'value':300,'request':100}.items():
                        value = args[0].get(key)
                        if value is not None and (not isinstance(value, str) or len(value) > limit):
                            emit('error', {'message': 'Geçersiz mesaj alanı.'})
                            return
                if admin:
                    user = current_principal()
                    allowed = bool(user) if function.__name__ == 'handle_admin_connect' else permitted(user, 'nav-chats')
                    if not allowed or not saved or saved['email'] != user['email'] or saved['group'] != user['group_id']:
                        emit('error', {'message': 'Bu işlem için yetkiniz yok.'})
                        return
            try:
                return function(*args, **kwargs)
            finally:
                if disconnecting:
                    socket_clients.pop(request.sid, None)
        return checked
    return decorate

def public_user(user):
    return {key:value for key,value in user.items() if key not in ('password','auth_version')}

def permissions(value):
    if not isinstance(value, list) or any(not isinstance(v, str) or v not in PERMISSIONS for v in value):
        abort(400, description='Geçersiz izinler.')
    return list(dict.fromkeys(value))
