# app/services/user_service.py
from app import data_manager
import bcrypt
import uuid
from datetime import datetime

def get_all_users():
    """Tüm kullanıcıların listesini döndürür."""
    return data_manager.users

def find_user_by_id(user_id):
    """ID ile bir kullanıcı bulur."""
    for user in data_manager.users:
        if user.get('id') == user_id:
            return user
    return None

def create_new_user(email, password, role):
    """Yeni bir kullanıcı oluşturur ve kaydeder."""
    if not email or not password:
        return False, "E-posta ve şifre gereklidir."
    if role not in ['admin', 'user']:
        return False, "Geçersiz rol belirtildi."

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # data_manager'daki mevcut add_user fonksiyonunu yeniden kullanalım
    # Bu, ilk kullanıcı yönetici kuralına uyulmasını sağlar.
    # Note: data_manager.add_user does not take role, it assigns group_admin by default.
    # This might need adjustment if admins are to be created via this service.
    # For now, we assume this service is for creating group_admins via signup.
    success, message = data_manager.add_user(email, hashed_password)
    return success, message

def update_user_role(user_id, new_role):
    """Bir kullanıcının rolünü günceller."""
    if new_role not in ['admin', 'user']:
        return False, "Geçersiz rol."

    user = find_user_by_id(user_id)
    if user:
        user['role'] = new_role
        data_manager._save_json(data_manager.users, data_manager.files['users'])
        return True, "Kullanıcı rolü güncellendi."
    return False, "Kullanıcı bulunamadı."

def delete_user_by_id(user_id_to_delete, admin_id):
    """Bir kullanıcıyı ID'sine göre siler."""
    if user_id_to_delete == admin_id:
        return False, "Yöneticiler kendilerini silemez."

    user_to_delete = find_user_by_id(user_id_to_delete)
    if user_to_delete:
        data_manager.users.remove(user_to_delete)
        data_manager._save_json(data_manager.users, data_manager.files['users'])
        return True, "Kullanıcı başarıyla silindi."
    return False, "Kullanıcı bulunamadı."
