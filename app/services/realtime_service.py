# app/services/realtime_service.py

# Başlangıçta bot aktif
bot_active = True

class RealtimeService:
    def get_bot_status(self):
        """Mevcut bot durumunu döndürür."""
        return bot_active

    def set_bot_status(self, is_active: bool):
        """Bot durumunu ayarlar."""
        global bot_active
        bot_active = is_active
        return bot_active
