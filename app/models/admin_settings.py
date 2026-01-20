"""Admin Settings Configuration"""

from app import db
from datetime import datetime


class AdminSettings(db.Model):
    """
    Stores application-wide admin settings.
    Only super_admin users can modify these settings.
    """

    __tablename__ = 'admin_settings'

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), nullable=False, unique=True, index=True)
    setting_value = db.Column(db.Text, nullable=True)
    setting_type = db.Column(db.String(20), default='string', nullable=False)  # string, boolean, integer, json
    description = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<AdminSettings {self.setting_key}: {self.setting_value}>'

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'setting_key': self.setting_key,
            'setting_value': self.get_typed_value(),
            'setting_type': self.setting_type,
            'description': self.description
        }

    def get_typed_value(self):
        """Get the setting value cast to the appropriate type"""
        if self.setting_value is None:
            return None

        if self.setting_type == 'boolean':
            return self.setting_value.lower() in ('true', '1', 'yes', 'on')
        elif self.setting_type == 'integer':
            try:
                return int(self.setting_value)
            except (ValueError, TypeError):
                return 0
        elif self.setting_type == 'json':
            import json
            try:
                return json.loads(self.setting_value)
            except (json.JSONDecodeError, TypeError):
                return {}
        else:  # string
            return self.setting_value

    def set_typed_value(self, value):
        """Set the setting value from a Python type"""
        if self.setting_type == 'boolean':
            self.setting_value = 'true' if value else 'false'
        elif self.setting_type == 'integer':
            self.setting_value = str(value)
        elif self.setting_type == 'json':
            import json
            self.setting_value = json.dumps(value)
        else:  # string
            self.setting_value = str(value) if value is not None else None

    @staticmethod
    def initialize_default_settings():
        """
        Initialize default admin settings.
        Should be called during database initialization.
        """
        default_settings = [
            {
                'setting_key': 'sensitive_info_filter_enabled',
                'setting_value': 'true',
                'setting_type': 'boolean',
                'description': 'Enable filtering of sensitive information (passwords, API keys, etc.) from user messages'
            },
            {
                'setting_key': 'lm_studio_vision_capable',
                'setting_value': 'true',
                'setting_type': 'boolean',
                'description': 'Enable vision/image support for LM Studio (requires vision-capable model loaded)'
            },
            {
                'setting_key': 'ollama_vision_capable',
                'setting_value': 'true',
                'setting_type': 'boolean',
                'description': 'Enable vision/image support for Ollama (requires vision-capable model like llava, gemma3, etc.)'
            }
        ]

        for setting_data in default_settings:
            existing = AdminSettings.query.filter_by(setting_key=setting_data['setting_key']).first()
            if not existing:
                setting = AdminSettings(**setting_data)
                db.session.add(setting)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_setting(key, default=None):
        """
        Get a setting value by key.

        Args:
            key: The setting key
            default: Default value if setting not found

        Returns:
            The typed setting value or default
        """
        setting = AdminSettings.query.filter_by(setting_key=key).first()
        if setting:
            return setting.get_typed_value()
        return default

    @staticmethod
    def set_setting(key, value, setting_type='string', description=None):
        """
        Set a setting value by key.

        Args:
            key: The setting key
            value: The value to set
            setting_type: The type of the setting (string, boolean, integer, json)
            description: Optional description of the setting

        Returns:
            The AdminSettings object
        """
        setting = AdminSettings.query.filter_by(setting_key=key).first()

        if not setting:
            setting = AdminSettings(
                setting_key=key,
                setting_type=setting_type,
                description=description
            )
            db.session.add(setting)

        setting.set_typed_value(value)

        if description:
            setting.description = description

        db.session.commit()
        return setting

    @staticmethod
    def is_sensitive_info_filter_enabled():
        """
        Check if sensitive information filtering is enabled.

        Returns:
            bool: True if enabled, False otherwise
        """
        return AdminSettings.get_setting('sensitive_info_filter_enabled', default=False)

    @staticmethod
    def is_lm_studio_vision_enabled():
        """
        Check if LM Studio vision/image support is enabled.

        Returns:
            bool: True if enabled, False otherwise
        """
        return AdminSettings.get_setting('lm_studio_vision_capable', default=False)

    @staticmethod
    def is_ollama_vision_enabled():
        """
        Check if Ollama vision/image support is enabled.

        Returns:
            bool: True if enabled, False otherwise
        """
        return AdminSettings.get_setting('ollama_vision_capable', default=False)

    @staticmethod
    def is_child_safety_enabled():
        """
        Check if child safety age-based prompts are enabled.

        Returns:
            bool: True if enabled, False otherwise
        """
        return AdminSettings.get_setting('child_safety_enabled', default=True)

    @staticmethod
    def get_child_system_prompt():
        """
        Get the system prompt for users under 12 years old.

        Returns:
            str or None: The child system prompt, or None if not set or disabled
        """
        if not AdminSettings.is_child_safety_enabled():
            return None
        return AdminSettings.get_setting('child_system_prompt', default=None)

    @staticmethod
    def get_teen_system_prompt():
        """
        Get the system prompt for users aged 12-17.

        Returns:
            str or None: The teen system prompt, or None if not set or disabled
        """
        if not AdminSettings.is_child_safety_enabled():
            return None
        return AdminSettings.get_setting('teen_system_prompt', default=None)

    @staticmethod
    def get_age_based_system_prompt(age_group: str):
        """
        Get the appropriate system prompt based on user's age group.

        Args:
            age_group: 'child', 'teen', 'adult', or 'unknown'

        Returns:
            str or None: The appropriate system prompt, or None for adults/unknown
        """
        if age_group == 'child':
            return AdminSettings.get_child_system_prompt()
        elif age_group == 'teen':
            return AdminSettings.get_teen_system_prompt()
        return None

    # ==================== Distilled Context ====================
    # When enabled, messages are automatically summarized and the summaries
    # are used as context for follow-up questions, enabling longer conversations.

    @staticmethod
    def is_distilled_context_enabled() -> bool:
        """
        Check if distilled context feature is enabled.

        When enabled, messages are automatically summarized after each exchange
        and the summaries are used as context instead of full messages.

        Returns:
            bool: True if enabled, False otherwise
        """
        return AdminSettings.get_setting('distilled_context_enabled', default=False)

    @staticmethod
    def set_distilled_context_enabled(enabled: bool) -> bool:
        """
        Enable or disable distilled context feature.

        Args:
            enabled: True to enable, False to disable

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            AdminSettings.set_setting(
                key='distilled_context_enabled',
                value=enabled,
                setting_type='boolean',
                description='Enable distilled context for longer conversations'
            )
            return True
        except Exception:
            return False

    # ==================== System Model IDs ====================
    # These are admin-level model IDs that define which models to use for each provider.
    # Stored as plain text (not encrypted) in the database.

    SUPPORTED_MODEL_PROVIDERS = ['gemini', 'openai', 'anthropic', 'xai', 'lm_studio', 'ollama']

    # Default model IDs (used when no setting exists in database)
    # Keep these in sync with scripts/migrations/add_model_id_settings.py
    # and run_compiled.py run_migrations()
    DEFAULT_MODEL_IDS = {
        'gemini': 'gemini-3-flash-preview',
        'openai': 'gpt-5-mini-2025-08-07',
        'anthropic': 'claude-haiku-4-5-20251001',
        'xai': 'grok-4-1-fast-non-reasoning-latest',
        'lm_studio': '',
        'ollama': ''
    }

    # Default URLs for local models
    DEFAULT_LOCAL_URLS = {
        'lm_studio': 'http://localhost:1234/v1/chat/completions',
        'ollama': 'http://localhost:11434/api/chat'
    }

    @staticmethod
    def get_system_model_id(provider: str) -> str:
        """
        Get the system-level model ID for a provider.

        Args:
            provider: Provider name ('gemini', 'openai', 'anthropic', 'xai', 'lm_studio', 'ollama')

        Returns:
            str: Model ID, or default if not set
        """
        if provider not in AdminSettings.SUPPORTED_MODEL_PROVIDERS:
            return ''

        setting_key = f'system_model_id_{provider}'
        model_id = AdminSettings.get_setting(setting_key, default=None)

        if model_id is None:
            # Return default model ID
            return AdminSettings.DEFAULT_MODEL_IDS.get(provider, '')

        return model_id

    @staticmethod
    def set_system_model_id(provider: str, model_id: str) -> bool:
        """
        Set the system-level model ID for a provider.

        Args:
            provider: Provider name ('gemini', 'openai', 'anthropic', 'xai', 'lm_studio', 'ollama')
            model_id: The model ID to store

        Returns:
            bool: True if successful, False otherwise
        """
        if provider not in AdminSettings.SUPPORTED_MODEL_PROVIDERS:
            return False

        setting_key = f'system_model_id_{provider}'

        try:
            AdminSettings.set_setting(
                key=setting_key,
                value=model_id.strip() if model_id else '',
                setting_type='string',
                description=f'System model ID for {provider}'
            )
            return True
        except Exception:
            return False

    @staticmethod
    def get_local_model_url(provider: str) -> str:
        """
        Get the system-level URL for a local model provider.

        Args:
            provider: Provider name ('lm_studio' or 'ollama')

        Returns:
            str: URL, or default if not set
        """
        if provider not in ['lm_studio', 'ollama']:
            return ''

        setting_key = f'system_model_url_{provider}'
        url = AdminSettings.get_setting(setting_key, default=None)

        if url is None:
            return AdminSettings.DEFAULT_LOCAL_URLS.get(provider, '')

        return url

    @staticmethod
    def set_local_model_url(provider: str, url: str) -> bool:
        """
        Set the system-level URL for a local model provider.

        Args:
            provider: Provider name ('lm_studio' or 'ollama')
            url: The URL to store

        Returns:
            bool: True if successful, False otherwise
        """
        if provider not in ['lm_studio', 'ollama']:
            return False

        setting_key = f'system_model_url_{provider}'

        try:
            AdminSettings.set_setting(
                key=setting_key,
                value=url.strip() if url else AdminSettings.DEFAULT_LOCAL_URLS.get(provider, ''),
                setting_type='string',
                description=f'System URL for {provider}'
            )
            return True
        except Exception:
            return False

    @staticmethod
    def get_all_system_model_settings() -> dict:
        """
        Get all system model IDs and local model URLs.

        Returns:
            dict: All model settings
        """
        result = {}

        # Cloud provider model IDs
        for provider in ['gemini', 'openai', 'anthropic', 'xai']:
            result[f'{provider}_model_id'] = AdminSettings.get_system_model_id(provider)

        # Local model settings
        for provider in ['lm_studio', 'ollama']:
            result[f'{provider}_model_id'] = AdminSettings.get_system_model_id(provider)
            result[f'{provider}_url'] = AdminSettings.get_local_model_url(provider)

        return result

    # ==================== System API Keys ====================
    # These are admin-level API keys that all users share by default.
    # Users can optionally override with their own keys in their profile.

    SUPPORTED_PROVIDERS = ['gemini', 'openai', 'anthropic', 'xai']

    @staticmethod
    def get_system_api_key(provider: str) -> str:
        """
        Get the system-level API key for a provider (decrypted).

        Args:
            provider: Provider name ('gemini', 'openai', 'anthropic', 'xai')

        Returns:
            str: Decrypted API key, or empty string if not set
        """
        from app.services.encryption_service import EncryptionService

        if provider not in AdminSettings.SUPPORTED_PROVIDERS:
            return ''

        setting_key = f'system_api_key_{provider}'
        encrypted_key = AdminSettings.get_setting(setting_key, default='')

        if not encrypted_key:
            return ''

        try:
            return EncryptionService.decrypt(encrypted_key)
        except Exception:
            return ''

    @staticmethod
    def set_system_api_key(provider: str, api_key: str) -> bool:
        """
        Set the system-level API key for a provider (encrypted).

        Args:
            provider: Provider name ('gemini', 'openai', 'anthropic', 'xai')
            api_key: The API key to store (will be encrypted)

        Returns:
            bool: True if successful, False otherwise
        """
        from app.services.encryption_service import EncryptionService

        if provider not in AdminSettings.SUPPORTED_PROVIDERS:
            return False

        setting_key = f'system_api_key_{provider}'

        # If empty key, remove the setting
        if not api_key:
            setting = AdminSettings.query.filter_by(setting_key=setting_key).first()
            if setting:
                db.session.delete(setting)
                db.session.commit()
            return True

        try:
            encrypted_key = EncryptionService.encrypt(api_key)
            AdminSettings.set_setting(
                key=setting_key,
                value=encrypted_key,
                setting_type='string',
                description=f'Encrypted system API key for {provider}'
            )
            return True
        except Exception:
            return False

    @staticmethod
    def has_system_api_key(provider: str) -> bool:
        """
        Check if a system-level API key exists for a provider.

        Args:
            provider: Provider name ('gemini', 'openai', 'anthropic', 'xai')

        Returns:
            bool: True if key exists, False otherwise
        """
        if provider not in AdminSettings.SUPPORTED_PROVIDERS:
            return False

        setting_key = f'system_api_key_{provider}'
        encrypted_key = AdminSettings.get_setting(setting_key, default='')
        return bool(encrypted_key)

    @staticmethod
    def get_masked_system_api_key(provider: str, show_chars: int = 8) -> str:
        """
        Get a masked version of the system API key for display.

        Args:
            provider: Provider name ('gemini', 'openai', 'anthropic', 'xai')
            show_chars: Number of characters to show at the start

        Returns:
            str: Masked API key (e.g., "sk-ant-a...") or empty string
        """
        from app.services.encryption_service import EncryptionService

        api_key = AdminSettings.get_system_api_key(provider)
        if not api_key:
            return ''

        return EncryptionService.mask_api_key(api_key, show_chars)

    @staticmethod
    def get_all_system_api_keys_status() -> dict:
        """
        Get status of all system API keys (whether they're configured).

        Returns:
            dict: Provider names mapped to their configuration status
        """
        return {
            provider: {
                'configured': AdminSettings.has_system_api_key(provider),
                'masked_key': AdminSettings.get_masked_system_api_key(provider)
            }
            for provider in AdminSettings.SUPPORTED_PROVIDERS
        }

    # ==================== Rate Limit Settings ====================
    # These settings allow admins to customize rate limits for various endpoints.
    # Rate limits can also be completely disabled via the toggle.

    # Default rate limits (used when no setting exists in database)
    # Keep these in sync with scripts/migrations/add_rate_limit_settings.py
    DEFAULT_RATE_LIMITS = {
        'chat': 100,              # requests per hour
        'attachment_upload': 50,   # requests per hour
        'document_upload': 20,     # requests per hour
        'improve_prompt': 30,      # requests per hour
        'login': 10,               # attempts per minute
        'register': 5,             # attempts per hour
        '2fa': 10                  # attempts per minute
    }

    @staticmethod
    def is_rate_limit_enabled() -> bool:
        """
        Check if rate limiting is enabled globally.

        Returns:
            bool: True if rate limiting is enabled, False otherwise
        """
        return AdminSettings.get_setting('rate_limit_enabled', default=True)

    @staticmethod
    def get_rate_limit(limit_name: str) -> int:
        """
        Get the rate limit value for a specific endpoint.

        Args:
            limit_name: Name of the rate limit ('chat', 'attachment_upload',
                       'document_upload', 'improve_prompt', 'login', 'register', '2fa')

        Returns:
            int: The rate limit value, or default if not set
        """
        if limit_name not in AdminSettings.DEFAULT_RATE_LIMITS:
            return 0

        setting_key = f'rate_limit_{limit_name}'
        value = AdminSettings.get_setting(setting_key, default=None)

        if value is None:
            return AdminSettings.DEFAULT_RATE_LIMITS.get(limit_name, 0)

        return int(value) if value else AdminSettings.DEFAULT_RATE_LIMITS.get(limit_name, 0)

    @staticmethod
    def set_rate_limit(limit_name: str, value: int) -> bool:
        """
        Set the rate limit value for a specific endpoint.

        Args:
            limit_name: Name of the rate limit
            value: The rate limit value

        Returns:
            bool: True if successful, False otherwise
        """
        if limit_name not in AdminSettings.DEFAULT_RATE_LIMITS:
            return False

        setting_key = f'rate_limit_{limit_name}'

        try:
            AdminSettings.set_setting(
                key=setting_key,
                value=int(value),
                setting_type='integer',
                description=f'Rate limit for {limit_name}'
            )
            return True
        except Exception:
            return False

    @staticmethod
    def get_all_rate_limits() -> dict:
        """
        Get all rate limit settings.

        Returns:
            dict: All rate limit settings including enabled status
        """
        result = {
            'enabled': AdminSettings.is_rate_limit_enabled()
        }

        for limit_name in AdminSettings.DEFAULT_RATE_LIMITS.keys():
            result[limit_name] = AdminSettings.get_rate_limit(limit_name)

        return result

    @staticmethod
    def get_rate_limit_string(limit_name: str) -> str:
        """
        Get the rate limit as a Flask-Limiter compatible string.

        Args:
            limit_name: Name of the rate limit

        Returns:
            str: Rate limit string (e.g., "100 per hour", "10 per minute")
        """
        value = AdminSettings.get_rate_limit(limit_name)

        # Login and 2FA are per minute, others are per hour
        if limit_name in ('login', '2fa'):
            return f"{value} per minute"
        else:
            return f"{value} per hour"
