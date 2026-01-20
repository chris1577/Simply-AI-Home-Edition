"""Two-Factor Authentication Backup Codes Model"""

from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from typing import List


class TwoFABackupCode(db.Model):
    """
    Store backup codes for 2FA recovery.
    Codes are hashed for security.
    """

    __tablename__ = 'twofa_backup_codes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    user = db.relationship('User', backref=db.backref('backup_codes', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True))

    def __repr__(self):
        return f'<TwoFABackupCode for User {self.user_id}>'

    @staticmethod
    def create_backup_codes(user_id: int, codes: List[str]):
        """
        Create backup codes for a user.

        Args:
            user_id: The user ID
            codes: List of plain text backup codes
        """
        for code in codes:
            # Normalize and hash the code
            normalized_code = code.replace('-', '').replace(' ', '').upper()
            code_hash = generate_password_hash(normalized_code)

            backup_code = TwoFABackupCode(
                user_id=user_id,
                code_hash=code_hash
            )
            db.session.add(backup_code)

    @staticmethod
    def verify_and_consume(user_id: int, code: str) -> bool:
        """
        Verify a backup code and mark it as used if valid.

        Args:
            user_id: The user ID
            code: The backup code to verify (normalized)

        Returns:
            True if code is valid and not used, False otherwise
        """
        # Get all unused backup codes for user
        backup_codes = TwoFABackupCode.query.filter_by(
            user_id=user_id,
            used=False
        ).all()

        # Try to match the code
        for backup_code in backup_codes:
            if check_password_hash(backup_code.code_hash, code):
                # Mark as used
                backup_code.used = True
                backup_code.used_at = datetime.utcnow()
                db.session.commit()
                return True

        return False
