# app/services/role_service.py
from app import data_manager
import uuid

def get_roles_for_group(group_id):
    """
    Retrieves all roles associated with a specific group ID.
    """
    if not group_id:
        return []
    return data_manager.get_roles_by_group(group_id)

def create_new_role(group_id, name, permissions):
    """
    Creates a new role for a group.
    """
    if not group_id or not name:
        return None, "Grup ID ve rol adı gereklidir."

    # Basic validation for permissions
    if not isinstance(permissions, list):
        return None, "İzinler bir liste olmalıdır."

    new_role = data_manager.add_role(group_id, name, permissions)
    return new_role, "Rol başarıyla oluşturuldu."

def update_existing_role(role_id, name, permissions, admin_group_id):
    """
    Updates an existing role, ensuring the admin has permission to do so.
    """
    # First, get all roles for the admin's group to verify ownership
    group_roles = data_manager.get_roles_by_group(admin_group_id)
    if not any(role.get('role_id') == role_id for role in group_roles):
        return False, "Bu rolü düzenleme yetkiniz yok."

    if not name:
        return False, "Rol adı boş olamaz."

    if not isinstance(permissions, list):
        return False, "İzinler bir liste olmalıdır."

    success = data_manager.update_role(role_id, name, permissions)
    if success:
        return True, "Rol başarıyla güncellendi."
    else:
        return False, "Rol bulunamadı."

def delete_existing_role(role_id, admin_group_id):
    """
    Deletes an existing role, ensuring the admin has permission.
    """
    # Verify ownership
    group_roles = data_manager.get_roles_by_group(admin_group_id)
    if not any(role.get('role_id') == role_id for role in group_roles):
        return False, "Bu rolü silme yetkiniz yok."

    success, message = data_manager.delete_role(role_id)
    return success, message
