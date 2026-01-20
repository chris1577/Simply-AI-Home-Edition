"""Model Visibility Configuration"""

from app import db
from datetime import datetime


class ModelVisibility(db.Model):
    """
    Tracks which AI models are visible to users in the application.
    Only super_admin users can modify these settings.
    """

    __tablename__ = 'model_visibility'

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False, unique=True, index=True)
    display_name = db.Column(db.String(100), nullable=False)
    icon_path = db.Column(db.String(255), nullable=True)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<ModelVisibility {self.provider}: {self.is_enabled}>'

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'provider': self.provider,
            'display_name': self.display_name,
            'icon_path': self.icon_path,
            'is_enabled': self.is_enabled,
            'sort_order': self.sort_order
        }

    @staticmethod
    def initialize_default_models():
        """
        Initialize default model visibility settings.
        Should be called during database initialization.
        """
        default_models = [
            {
                'provider': 'gemini',
                'display_name': 'Gemini',
                'icon_path': '/static/images/gemini.png',
                'is_enabled': True,
                'sort_order': 1
            },
            {
                'provider': 'xai',
                'display_name': 'Grok',
                'icon_path': '/static/images/grok.png',
                'is_enabled': True,
                'sort_order': 2
            },
            {
                'provider': 'anthropic',
                'display_name': 'Claude',
                'icon_path': '/static/images/claude.png',
                'is_enabled': True,
                'sort_order': 3
            },
            {
                'provider': 'openai',
                'display_name': 'ChatGPT',
                'icon_path': '/static/images/chatgpt.png',
                'is_enabled': True,
                'sort_order': 4
            },
            {
                'provider': 'simply_lm_studio',
                'display_name': 'LM Studio',
                'icon_path': '/static/images/lmstudio.png',
                'is_enabled': True,
                'sort_order': 5
            },
            {
                'provider': 'simply_ollama',
                'display_name': 'Ollama',
                'icon_path': '/static/images/ollama.png',
                'is_enabled': True,
                'sort_order': 6
            }
        ]

        for model_data in default_models:
            existing = ModelVisibility.query.filter_by(provider=model_data['provider']).first()
            if not existing:
                model = ModelVisibility(**model_data)
                db.session.add(model)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_enabled_models():
        """
        Get all enabled models sorted by sort_order.

        Returns:
            list: List of enabled model dictionaries
        """
        models = ModelVisibility.query.filter_by(is_enabled=True).order_by(ModelVisibility.sort_order).all()
        return [model.to_dict() for model in models]

    @staticmethod
    def get_all_models():
        """
        Get all models sorted by sort_order.

        Returns:
            list: List of all model dictionaries
        """
        models = ModelVisibility.query.order_by(ModelVisibility.sort_order).all()
        return [model.to_dict() for model in models]

    @staticmethod
    def is_model_enabled(provider):
        """
        Check if a specific model is enabled.

        Args:
            provider: The provider identifier

        Returns:
            bool: True if model is enabled, False otherwise
        """
        model = ModelVisibility.query.filter_by(provider=provider).first()
        return model.is_enabled if model else False
