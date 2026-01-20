import os
from dotenv import load_dotenv

# Force .env file to override system environment variables
# This ensures .env always takes precedence
load_dotenv(override=True)


def get_database_url():
    """
    Get database URL based on DB_TYPE environment variable.
    Supports easy switching between sqlite and sqlexpress.

    Set DB_TYPE in .env file:
    - DB_TYPE=sqlite      -> Uses SQLITE_URL (default: sqlite:///simplyai.db)
    - DB_TYPE=sqlexpress  -> Uses SQLEXPRESS_URL (SQL Server Express)
    - If DB_TYPE is not set, falls back to DATABASE_URL or sqlite default
    """
    db_type = os.getenv('DB_TYPE', '').lower()

    if db_type == 'sqlexpress':
        return os.getenv('SQLEXPRESS_URL',
            'mssql+pyodbc:///?odbc_connect=DRIVER%3D%7BODBC+Driver+17+for+SQL+Server%7D%3BSERVER%3Dlocalhost%5CSQLEXPRESS%3BDATABASE%3Dsimplyai%3BTrusted_Connection%3Dyes')
    elif db_type == 'sqlite':
        return os.getenv('SQLITE_URL', 'sqlite:///simplyai.db')
    else:
        # Fallback to DATABASE_URL for backwards compatibility or custom databases
        return os.getenv('DATABASE_URL', 'sqlite:///simplyai.db')


class Config:
    """Base configuration"""

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-this')

    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # Session configuration
    PERMANENT_SESSION_LIFETIME = int(os.getenv('PERMANENT_SESSION_LIFETIME', 3600))
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'
    SESSION_COOKIE_HTTPONLY = os.getenv('SESSION_COOKIE_HTTPONLY', 'True') == 'True'
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Rate limiting (uses in-memory storage - sufficient for single-instance home edition)
    RATELIMIT_STORAGE_URL = 'memory://'
    RATELIMIT_ENABLED = True

    # AI Provider Configuration
    # Note: API keys AND model IDs are stored in the database via AdminSettings.
    # Configure them through the Settings page (super_admin only).
    # API keys are encrypted; model IDs are stored as plain text.
    #
    # The following environment variables are NO LONGER USED:
    # - GEMINI_MODEL_ID, OPENAI_MODEL_ID, ANTHROPIC_MODEL_ID, XAI_MODEL_ID
    # - LM_STUDIO_URL, LM_STUDIO_MODEL_ID, OLLAMA_URL, OLLAMA_MODEL_ID
    #
    # Run the migration: python scripts/migrations/add_model_id_settings.py
    # Then configure via Settings page.

    # Gemini API (legacy - no longer used, kept for reference)
    GEMINI_API_URL = os.getenv("GEMINI_API_URL", "")

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'app.log')

    # File Uploads
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB max request size


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = get_database_url()
    # Log SQL queries in development (can be disabled via SQLALCHEMY_ECHO=false env var)
    SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'true').lower() == 'true'

    # Rate limiting enabled with memory storage
    RATELIMIT_STORAGE_URL = 'memory://'
    RATELIMIT_ENABLED = True


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv('TEST_DATABASE_URL', 'sqlite:///test.db')
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SESSION_COOKIE_SECURE = True  # Force HTTPS in production

    # Ensure critical settings are set in production
    @classmethod
    def validate(cls):
        if not os.getenv('SECRET_KEY'):
            raise ValueError("SECRET_KEY must be set in production")
        if not os.getenv('DATABASE_URL'):
            raise ValueError("DATABASE_URL must be set in production")


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """Get configuration based on environment"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    return config.get(config_name, config['default'])
