from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from typing import Optional


class User(UserMixin, db.Model):
    """User model for authentication and user management"""

    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # User status
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)

    # 2FA
    twofa_enabled = db.Column(db.Boolean, default=False)
    twofa_secret = db.Column(db.String(32), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # Child safety - date of birth for age-based content filtering
    date_of_birth = db.Column(db.Date, nullable=True)

    # Account lockout for failed login attempts
    failed_login_attempts = db.Column(db.Integer, default=0)
    account_locked_until = db.Column(db.DateTime, nullable=True)

    # Single session enforcement - only one device can be logged in at a time
    session_token = db.Column(db.String(64), nullable=True, index=True)

    # Relationships
    chats = db.relationship('Chat', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')
    roles = db.relationship('Role', secondary='user_roles', backref='users', lazy='dynamic')

    def set_password(self, password, check_history=False):
        """
        Hash and set user password.

        Args:
            password: The new password
            check_history: Whether to check password history (default False for new users)

        Returns:
            tuple: (success: bool, error_message: str or None)
        """
        # Check password history if requested
        if check_history and self.id:
            from app.models.password_history import PasswordHistory

            if PasswordHistory.check_password_reuse(self.id, password, history_limit=5):
                return False, "Password has been used recently. Please choose a different password."

        # Hash and set the new password
        new_hash = generate_password_hash(password)

        # Save old password to history if user already exists
        if self.id and self.password_hash:
            from app.models.password_history import PasswordHistory
            PasswordHistory.add_password_to_history(self.id, self.password_hash)

            # Clean up old history entries (keep last 10)
            PasswordHistory.cleanup_old_history(self.id, keep_count=10)

        self.password_hash = new_hash
        return True, None

    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)

    def is_account_locked(self):
        """Check if account is currently locked"""
        if self.account_locked_until is None:
            return False
        return datetime.utcnow() < self.account_locked_until

    def increment_failed_login(self):
        """Increment failed login attempts and lock account if threshold reached"""
        self.failed_login_attempts += 1

        # Lock account after 5 failed attempts for 15 minutes
        MAX_ATTEMPTS = 5
        LOCKOUT_DURATION_MINUTES = 15

        if self.failed_login_attempts >= MAX_ATTEMPTS:
            from datetime import timedelta
            self.account_locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)

    def reset_failed_login(self):
        """Reset failed login attempts after successful login"""
        self.failed_login_attempts = 0
        self.account_locked_until = None

    def generate_session_token(self):
        """Generate a new unique session token for single-session enforcement"""
        import secrets
        self.session_token = secrets.token_hex(32)  # 64 character hex string
        return self.session_token

    def validate_session_token(self, token):
        """Check if the provided session token matches the stored one"""
        if not self.session_token or not token:
            return False
        return self.session_token == token

    def invalidate_session(self):
        """Invalidate the current session token (for logout)"""
        self.session_token = None

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role"""
        from app.models.rbac import Role
        return self.roles.filter_by(name=role_name).first() is not None

    def has_permission(self, permission_name: str) -> bool:
        """Check if user has a specific permission through any of their roles"""
        from app.models.rbac import Permission

        # Super admins have all permissions
        if self.has_role('super_admin'):
            return True

        # Check if any of the user's roles have this permission
        for role in self.roles:
            if role.has_permission(permission_name):
                return True

        return False

    def add_role(self, role):
        """Add a role to this user"""
        if not self.has_role(role.name):
            self.roles.append(role)

    def remove_role(self, role):
        """Remove a role from this user"""
        if self.has_role(role.name):
            self.roles.remove(role)

    def get_highest_role_level(self) -> int:
        """Get the highest role level for this user"""
        if self.roles.count() == 0:
            return 0

        return max(role.level for role in self.roles)

    def get_age(self) -> Optional[int]:
        """
        Calculate user's current age from date of birth.

        Returns:
            int: User's age in years, or None if DOB not set
        """
        if not self.date_of_birth:
            return None
        today = date.today()
        born = self.date_of_birth
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

    def get_age_group(self) -> str:
        """
        Classify user into age groups for child safety content filtering.

        Returns:
            str: 'child' (under 12), 'teen' (12-17), 'adult' (18+), or 'unknown' (no DOB)
        """
        age = self.get_age()
        if age is None:
            return 'unknown'
        if age < 12:
            return 'child'
        if age < 18:
            return 'teen'
        return 'adult'

    def to_dict(self, include_email=False, include_age_group=False):
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'roles': [role.name for role in self.roles]
        }
        if include_email:
            data['email'] = self.email
        if include_age_group:
            data['age_group'] = self.get_age_group()
        return data

    def __repr__(self):
        return f'<User {self.username}>'
