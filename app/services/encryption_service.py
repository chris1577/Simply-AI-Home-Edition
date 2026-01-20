"""
Encryption service for secure storage of API keys
Uses Fernet symmetric encryption with the Flask SECRET_KEY
"""
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
from flask import current_app


class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""

    @staticmethod
    def _get_cipher():
        """
        Generate a Fernet cipher from the Flask SECRET_KEY

        Returns:
            Fernet: Cipher instance for encryption/decryption
        """
        secret_key = current_app.config.get('SECRET_KEY')
        if not secret_key:
            raise ValueError("SECRET_KEY not configured in Flask app")

        # Use PBKDF2HMAC to derive a proper key from SECRET_KEY
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'simply_ai_salt_v1',  # Static salt for consistency
            iterations=100000,
            backend=default_backend()
        )

        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        return Fernet(key)

    @staticmethod
    def encrypt(plaintext: str) -> str:
        """
        Encrypt plaintext string

        Args:
            plaintext: String to encrypt

        Returns:
            str: Encrypted string (base64 encoded)
        """
        if not plaintext:
            return ""

        cipher = EncryptionService._get_cipher()
        encrypted_bytes = cipher.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    @staticmethod
    def decrypt(encrypted_text: str) -> str:
        """
        Decrypt encrypted string

        Args:
            encrypted_text: Encrypted string (base64 encoded)

        Returns:
            str: Decrypted plaintext string
        """
        if not encrypted_text:
            return ""

        try:
            cipher = EncryptionService._get_cipher()
            decrypted_bytes = cipher.decrypt(encrypted_text.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            current_app.logger.error(f"Decryption error: {str(e)}")
            raise ValueError("Failed to decrypt data. The encryption key may have changed.")

    @staticmethod
    def mask_api_key(api_key: str, show_chars: int = 8) -> str:
        """
        Mask an API key for display purposes

        Args:
            api_key: The API key to mask
            show_chars: Number of characters to show at the start

        Returns:
            str: Masked API key (e.g., "sk-ant-a...")
        """
        if not api_key or len(api_key) < show_chars:
            return ""
        return api_key[:show_chars] + "..."
