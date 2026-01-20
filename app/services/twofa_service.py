"""Two-Factor Authentication (2FA) Service using TOTP"""

import pyotp
import qrcode
import io
import base64
import secrets
from typing import Tuple, List
from app import db
from app.models.user import User


class TwoFAService:
    """Service for managing TOTP-based two-factor authentication"""

    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new TOTP secret key.

        Returns:
            Base32-encoded secret string
        """
        return pyotp.random_base32()

    @staticmethod
    def get_totp_uri(user: User, issuer_name: str = "Enterprise AI GUI") -> str:
        """
        Generate TOTP provisioning URI for QR code.

        Args:
            user: The User object
            issuer_name: The application name to display in authenticator apps

        Returns:
            TOTP URI string
        """
        if not user.twofa_secret:
            raise ValueError("User does not have a 2FA secret")

        totp = pyotp.TOTP(user.twofa_secret)
        return totp.provisioning_uri(
            name=user.email,
            issuer_name=issuer_name
        )

    @staticmethod
    def generate_qr_code(user: User) -> str:
        """
        Generate QR code image as base64 string for 2FA setup.

        Args:
            user: The User object

        Returns:
            Base64-encoded PNG image string
        """
        uri = TwoFAService.get_totp_uri(user)

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"

    @staticmethod
    def verify_totp_code(user: User, code: str) -> bool:
        """
        Verify a TOTP code for a user.

        Args:
            user: The User object
            code: The 6-digit TOTP code to verify

        Returns:
            True if code is valid, False otherwise
        """
        if not user.twofa_secret:
            return False

        # Remove spaces and validate format
        code = code.replace(' ', '').replace('-', '')

        if not code.isdigit() or len(code) != 6:
            return False

        totp = pyotp.TOTP(user.twofa_secret)

        # Verify with a window of ±1 time step (30 seconds) to account for clock drift
        return totp.verify(code, valid_window=1)

    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """
        Generate backup codes for 2FA recovery.

        Args:
            count: Number of backup codes to generate (default 10)

        Returns:
            List of backup code strings
        """
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = secrets.token_hex(4).upper()
            # Format as XXXX-XXXX for readability
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)

        return codes

    @staticmethod
    def enable_2fa_for_user(user: User) -> Tuple[str, List[str], str]:
        """
        Enable 2FA for a user.

        Args:
            user: The User object

        Returns:
            Tuple of (secret, backup_codes, qr_code_base64)
        """
        # Generate new secret
        secret = TwoFAService.generate_secret()
        user.twofa_secret = secret

        # Generate QR code
        qr_code = TwoFAService.generate_qr_code(user)

        # Generate backup codes
        backup_codes = TwoFAService.generate_backup_codes()

        # Store hashed backup codes in database
        from app.models.twofa_backup import TwoFABackupCode
        TwoFABackupCode.create_backup_codes(user.id, backup_codes)

        # Mark 2FA as enabled
        user.twofa_enabled = True
        db.session.commit()

        return secret, backup_codes, qr_code

    @staticmethod
    def disable_2fa_for_user(user: User):
        """
        Disable 2FA for a user.

        Args:
            user: The User object
        """
        user.twofa_enabled = False
        user.twofa_secret = None

        # Delete all backup codes
        from app.models.twofa_backup import TwoFABackupCode
        TwoFABackupCode.query.filter_by(user_id=user.id).delete()

        db.session.commit()

    @staticmethod
    def verify_backup_code(user: User, code: str) -> bool:
        """
        Verify and consume a backup code.

        Args:
            user: The User object
            code: The backup code to verify

        Returns:
            True if code is valid and not used, False otherwise
        """
        from app.models.twofa_backup import TwoFABackupCode

        # Normalize code format
        code = code.replace(' ', '').replace('-', '').upper()

        return TwoFABackupCode.verify_and_consume(user.id, code)

    @staticmethod
    def get_remaining_backup_codes(user: User) -> int:
        """
        Get count of remaining unused backup codes.

        Args:
            user: The User object

        Returns:
            Number of remaining backup codes
        """
        from app.models.twofa_backup import TwoFABackupCode

        return TwoFABackupCode.query.filter_by(
            user_id=user.id,
            used=False
        ).count()

    @staticmethod
    def regenerate_backup_codes(user: User) -> List[str]:
        """
        Regenerate backup codes for a user.

        Args:
            user: The User object

        Returns:
            List of new backup codes
        """
        from app.models.twofa_backup import TwoFABackupCode

        # Delete old backup codes
        TwoFABackupCode.query.filter_by(user_id=user.id).delete()

        # Generate new codes
        backup_codes = TwoFAService.generate_backup_codes()
        TwoFABackupCode.create_backup_codes(user.id, backup_codes)

        db.session.commit()

        return backup_codes
