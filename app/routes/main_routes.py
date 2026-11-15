# app/routes/main_routes.py
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from config import Config
import bcrypt
import secrets
import hmac
import re
from app.services.security import user_stamp, current_principal
import time
from functools import wraps
from app.services.auth_service import generate_token
from app import data_manager

main_bp = Blueprint('main', __name__)
login_manager = LoginManager()
login_manager.login_view = 'main.admin_login'
login_manager.login_message = "Bu sayfayı görüntülemek için lütfen giriş yapın."
login_manager.login_message_category = "info"

# Helper decorator for role-based access
def panel_access_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_principal():
            return redirect(url_for('main.admin_login'))

        if current_user.role not in ['admin', 'group_admin', 'user']:
            flash("Bu sayfaya erişim yetkiniz yok.", "error")
            return redirect(url_for('main.index'))

        return f(*args, **kwargs)
    return decorated_function

class User(UserMixin):
    def __init__(self, email, role='user', group_id=None, permissions=None):
        self.id = email
        self.role = role
        self.group_id = group_id
        self.permissions = permissions if permissions is not None else []
        user_data = data_manager.get_user(email)
        self.auth_stamp = user_stamp(user_data) if user_data else ''

    def get_id(self):
        return self.id + '|' + self.auth_stamp

@login_manager.user_loader
def load_user(user_id):
    email, separator, stamp = user_id.rpartition('|')
    user_data = data_manager.get_user(email) if separator else None
    if user_data and hmac.compare_digest(stamp, user_stamp(user_data)):
        return User(
            email=user_data['email'],
            role=user_data.get('role', 'user'),
            group_id=user_data.get('group_id'),
            permissions=user_data.get('permissions', [])
        )
    return None

@main_bp.route('/')
def index():
    session.pop('conversation_state', None)
    settings = data_manager.get_settings()
    theme_settings = settings.get('theme', {})
    return render_template("index.html", theme_settings=theme_settings)

@main_bp.route('/desteksayfasi')
def desteksayfasi():
    return render_template("desteksayfasi.html")

@main_bp.route('/admin')
@login_required
@panel_access_required
def admin_panel():
    api_token = generate_token(current_user.id)
    cache_version = int(time.time())
    users = data_manager.users # Keep this for the initial login/signup view logic

    # Pass the current user's role and permissions to the template
    user_permissions = {
        "role": current_user.role,
        "permissions": current_user.permissions
    }

    return render_template(
        "admin.html",
        api_token=api_token,
        chatbot_url=url_for('main.index',group=data_manager.public_group_id(current_user.group_id)),
        cache_version=cache_version,
        users=users,
        user_permissions=user_permissions
    )

@main_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('main.admin_panel'))

    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password')

        user_data = data_manager.get_user(email)

        if isinstance(password,str) and len(password.encode('utf-8'))<=72 and user_data and bcrypt.checkpw(password.encode('utf-8'), user_data['password'].encode('utf-8')):
            user = User(user_data['email'], user_data.get('role','user'), user_data.get('group_id'), user_data.get('permissions',[]))
            session.clear()
            login_user(user, remember=True)
            return redirect(url_for('main.admin_panel'))
        else:
            flash('Geçersiz e-posta veya şifre.', 'error')

    # Check if any user exists. If not, maybe redirect to signup?
    # For now, just render the template. The JS will handle showing/hiding forms.
    users = data_manager.users
    return render_template("admin.html", users=users, user_permissions={})

@main_bp.route('/signup', methods=['POST'])
def signup():
    email = request.form.get('email','').strip().lower()
    password = request.form.get('password')

    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or not isinstance(password,str) or not 12<=len(password.encode('utf-8'))<=72:
        flash('Geçerli e-posta ve 12–72 bayt uzunluğunda şifre gereklidir.', 'error')
        return redirect(url_for('main.admin_login'))

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    success, message = data_manager.add_user(email, hashed_password)

    if success:
        flash('Hesap başarıyla oluşturuldu. Lütfen giriş yapın.', 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('main.admin_login'))

@main_bp.route('/logout')
@login_required
def logout():
    user = data_manager.get_user(current_user.id)
    if user:
        with data_manager._lock:
            user['auth_version'] = secrets.token_urlsafe(24)
            data_manager._save_json(data_manager.users,data_manager.files['users'])
    logout_user()
    session.clear()
    return redirect(url_for('main.admin_login'))
