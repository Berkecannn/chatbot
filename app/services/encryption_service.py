import os
from cryptography.fernet import Fernet
from config import Config

class EncryptionService:
    def __init__(self):
        key = Config.ENCRYPTION_KEY
        if not key:
            raise ValueError("ENCRYPTION_KEY is not set in the environment.")
        self.fernet = Fernet(key.encode())

    def encrypt(self, data: str) -> str:
        if not data:
            return ""
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        if not encrypted_data:
            return ""
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception:
            # Handle cases where the data is not valid encrypted data
            # This could be because it's an old, unencrypted value or invalid.
            # Returning it as-is might be an option, but for credentials,
            # returning empty is safer.
            return ""

# A single instance to be used across the application
# This ensures we don't re-initialize the class unnecessarily
encryption_service = EncryptionService()
