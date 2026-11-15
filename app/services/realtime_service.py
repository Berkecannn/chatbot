# app/services/realtime_service.py

# Başlangıçta bot aktif
bot_active = True

class RealtimeService:
    def __init__(self):
        self._customer_status = {}

    def get_bot_status(self):
        """Mevcut bot durumunu döndürür."""
        from app import data_manager
        return self._customer_status.get(data_manager.current_group(), True)

    def set_bot_status(self, is_active: bool):
        """Bot durumunu ayarlar."""
        from app import data_manager
        self._customer_status[data_manager.current_group()] = is_active
        return is_active
