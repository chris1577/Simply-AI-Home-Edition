"""Password history model for tracking password changes"""

from app import db
from datetime import datetime
from werkzeug.security import check_password_hash


class PasswordHistory(db.Model):
    """
    Track user password history to prevent password reuse.
    Stores hashed passwords for security.
    """

    __tablename__ = 'password_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    user = db.relationship('User', backref=db.backref('password_history', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True))

    def __repr__(self):
        return f'<PasswordHistory for User {self.user_id}>'

    @staticmethod
    def check_password_reuse(user_id: int, new_password: str, history_limit: int = 5) -> bool:
        """
        Check if a new password has been used recently.

        Args:
            user_id: The user ID
            new_password: The new password to check
            history_limit: Number of previous passwords to check (default 5)

        Returns:
            True if password is being reused, False otherwise
        """
        # Get the last N password hashes for this user
        history = PasswordHistory.query.filter_by(user_id=user_id)\
            .order_by(PasswordHistory.created_at.desc())\
            .limit(history_limit)\
            .all()

        # Check if new password matches any recent password
        for entry in history:
            if check_password_hash(entry.password_hash, new_password):
                return True

        return False

    @staticmethod
    def add_password_to_history(user_id: int, password_hash: str):
        """
        Add a password hash to the user's history.

        Args:
            user_id: The user ID
            password_hash: The hashed password to store
        """
        entry = PasswordHistory(user_id=user_id, password_hash=password_hash)
        db.session.add(entry)

    @staticmethod
    def cleanup_old_history(user_id: int, keep_count: int = 10):
        """
        Remove old password history entries, keeping only the most recent ones.

        Args:
            user_id: The user ID
            keep_count: Number of recent passwords to keep (default 10)
        """
        # Get all history entries for user, ordered by date
        all_history = PasswordHistory.query.filter_by(user_id=user_id)\
            .order_by(PasswordHistory.created_at.desc())\
            .all()

        # If we have more than keep_count entries, delete the oldest ones
        if len(all_history) > keep_count:
            to_delete = all_history[keep_count:]
            for entry in to_delete:
                db.session.delete(entry)
