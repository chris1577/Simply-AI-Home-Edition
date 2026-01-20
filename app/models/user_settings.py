"""User settings model for storing user preferences and configurations"""
from app import db
from datetime import datetime


class UserSettings(db.Model):
    """User settings for local models and preferences"""

    __tablename__ = 'user_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)

    # Local Model Settings
    lm_studio_url = db.Column(db.String(255), default='http://localhost:1234/v1/chat/completions')
    lm_studio_model_id = db.Column(db.String(100), default='')
    ollama_url = db.Column(db.String(255), default='http://localhost:11434/api/chat')
    ollama_model_id = db.Column(db.String(100), default='')

    # API Provider Model Settings
    gemini_model_id = db.Column(db.String(100), default='')
    openai_model_id = db.Column(db.String(100), default='')
    anthropic_model_id = db.Column(db.String(100), default='')
    xai_model_id = db.Column(db.String(100), default='')

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('settings', uselist=False, lazy=True, cascade='all, delete-orphan', passive_deletes=True))

    @classmethod
    def get_or_create(cls, user_id):
        """
        Get existing settings or create new ones with defaults

        Args:
            user_id: User ID

        Returns:
            UserSettings: User settings instance
        """
        settings = cls.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = cls(user_id=user_id)
            db.session.add(settings)
            db.session.commit()
        return settings

    def to_dict(self):
        """
        Convert to dictionary

        Returns:
            dict: UserSettings data
        """
        return {
            'lm_studio_url': self.lm_studio_url,
            'lm_studio_model_id': self.lm_studio_model_id,
            'ollama_url': self.ollama_url,
            'ollama_model_id': self.ollama_model_id,
            'gemini_model_id': self.gemini_model_id,
            'openai_model_id': self.openai_model_id,
            'anthropic_model_id': self.anthropic_model_id,
            'xai_model_id': self.xai_model_id,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def update_from_dict(self, data):
        """
        Update settings from dictionary

        Args:
            data: Dictionary containing settings to update
        """
        if 'lm_studio_url' in data:
            self.lm_studio_url = data['lm_studio_url'].strip() or 'http://localhost:1234/v1/chat/completions'

        if 'lm_studio_model_id' in data:
            self.lm_studio_model_id = data['lm_studio_model_id'].strip()

        if 'ollama_url' in data:
            self.ollama_url = data['ollama_url'].strip() or 'http://localhost:11434/api/chat'

        if 'ollama_model_id' in data:
            self.ollama_model_id = data['ollama_model_id'].strip()

        if 'gemini_model_id' in data:
            self.gemini_model_id = data['gemini_model_id'].strip()

        if 'openai_model_id' in data:
            self.openai_model_id = data['openai_model_id'].strip()

        if 'anthropic_model_id' in data:
            self.anthropic_model_id = data['anthropic_model_id'].strip()

        if 'xai_model_id' in data:
            self.xai_model_id = data['xai_model_id'].strip()

        self.updated_at = datetime.utcnow()

    def __repr__(self):
        return f'<UserSettings for User {self.user_id}>'
