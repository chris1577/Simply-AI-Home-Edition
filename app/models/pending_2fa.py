"""Pending 2FA Verification Model"""

from app import db
from datetime import datetime, timedelta
import secrets


class Pending2FAVerification(db.Model):
    """
    Track pending 2FA verifications during login.
    These are temporary and expire after 5 minutes.
    """

    __tablename__ = 'pending_2fa_verifications'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    verified = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Pending2FA for User {self.user_id}>'

    @staticmethod
    def create_pending_verification(user_id: int) -> str:
        """
        Create a pending 2FA verification token.

        Args:
            user_id: The user ID

        Returns:
            The verification token
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        pending = Pending2FAVerification(
            token=token,
            user_id=user_id,
            expires_at=expires_at
        )

        db.session.add(pending)
        db.session.commit()

        return token

    @staticmethod
    def verify_token(token: str) -> 'Pending2FAVerification':
        """
        Verify a pending 2FA token.

        Args:
            token: The verification token

        Returns:
            Pending2FAVerification object if valid, None otherwise
        """
        pending = Pending2FAVerification.query.filter_by(token=token).first()

        if not pending:
            return None

        # Check if expired
        if datetime.utcnow() > pending.expires_at:
            db.session.delete(pending)
            db.session.commit()
            return None

        # Check if already verified
        if pending.verified:
            return None

        return pending

    @staticmethod
    def mark_verified(token: str):
        """
        Mark a token as verified and delete it.

        Args:
            token: The verification token
        """
        pending = Pending2FAVerification.query.filter_by(token=token).first()
        if pending:
            db.session.delete(pending)
            db.session.commit()

    @staticmethod
    def cleanup_expired():
        """
        Clean up expired pending verifications.
        Should be run periodically.
        """
        Pending2FAVerification.query.filter(
            Pending2FAVerification.expires_at < datetime.utcnow()
        ).delete()
        db.session.commit()
