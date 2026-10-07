# app/routes/main_routes.py
from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from config import Config
import bcrypt
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
        if not current_user.is_authenticated:
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

@login_manager.user_loader
def load_user(user_id):
    user_data = data_manager.get_user(user_id)
    if user_data:
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
        cache_version=cache_version,
        users=users,
        user_permissions=user_permissions
    )

@main_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('main.admin_panel'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user_data = data_manager.get_user(email)

        if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data['password'].encode('utf-8')):
            user = load_user(user_data['email'])
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
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        flash('E-posta ve şifre gereklidir.', 'error')
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
    logout_user()
    return redirect(url_for('main.admin_login'))
