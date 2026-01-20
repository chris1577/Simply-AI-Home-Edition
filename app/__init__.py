import logging
from logging.handlers import RotatingFileHandler
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import config, get_config

# Initialize Flask extensions
db = SQLAlchemy()
login_manager = LoginManager()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10000 per day", "1000 per hour"],  # Higher limits for development
    storage_uri="memory://"  # Will be overridden by config
)


# ==================== Dynamic Rate Limit Functions ====================
# These functions return rate limit strings from database settings.
# They are used as callables in @limiter.limit() decorators.

def get_dynamic_rate_limit(limit_name: str):
    """
    Create a callable that returns the rate limit string for a given endpoint.
    This allows rate limits to be configured dynamically from the database.

    Args:
        limit_name: Name of the rate limit (e.g., 'chat', 'login')

    Returns:
        A callable that returns the rate limit string
    """
    def _get_limit():
        from app.models.admin_settings import AdminSettings
        try:
            # Check if rate limiting is disabled
            if not AdminSettings.is_rate_limit_enabled():
                # Return a very high limit effectively disabling rate limiting
                return "1000000 per hour"
            return AdminSettings.get_rate_limit_string(limit_name)
        except Exception:
            # Fallback to defaults if database not available
            defaults = {
                'chat': '100 per hour',
                'attachment_upload': '50 per hour',
                'document_upload': '20 per hour',
                'improve_prompt': '30 per hour',
                'login': '10 per minute',
                'register': '5 per hour',
                '2fa': '10 per minute'
            }
            return defaults.get(limit_name, '100 per hour')
    return _get_limit


# Pre-defined rate limit callables for use in route decorators
rate_limit_chat = get_dynamic_rate_limit('chat')
rate_limit_attachment_upload = get_dynamic_rate_limit('attachment_upload')
rate_limit_document_upload = get_dynamic_rate_limit('document_upload')
rate_limit_improve_prompt = get_dynamic_rate_limit('improve_prompt')
rate_limit_login = get_dynamic_rate_limit('login')
rate_limit_register = get_dynamic_rate_limit('register')
rate_limit_2fa = get_dynamic_rate_limit('2fa')


def create_app(config_name=None):
    """Application factory pattern"""

    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static'
    )

    # Load configuration
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    config_obj = get_config(config_name)
    app.config.from_object(config_obj)

    # Validate production config
    if config_name == 'production':
        config_obj.validate()

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Configure rate limiter only if enabled
    if app.config.get('RATELIMIT_ENABLED', True):
        limiter.init_app(app)

    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))

    # Single session enforcement - validate session token on every request
    @app.before_request
    def validate_session_token():
        from flask import session, request, redirect, url_for, jsonify
        from flask_login import current_user, logout_user

        # Skip validation for unauthenticated users
        if not current_user.is_authenticated:
            return

        # Skip validation for auth routes (login, logout, register, etc.)
        # to prevent redirect loops
        if request.endpoint and (
            request.endpoint.startswith('auth.') or
            request.endpoint == 'static'
        ):
            return

        # Get session token from Flask session
        stored_token = session.get('session_token')

        # Validate token against database
        if not current_user.validate_session_token(stored_token):
            # Token mismatch - another device logged in
            # Clear the session
            session.clear()
            logout_user()

            # Return appropriate response based on request type
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({
                    'error': 'Session invalidated - logged in from another device',
                    'code': 'SESSION_INVALIDATED',
                    'redirect': url_for('auth.login')
                }), 401

            # Redirect to login for regular requests
            return redirect(url_for('auth.login'))

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    # Configure logging
    configure_logging(app)

    # Note: Database tables are created via init_db.py script
    # NOT automatically on app creation to ensure all models are loaded first
    # with app.app_context():
    #     db.create_all()

    return app


def register_blueprints(app):
    """Register Flask blueprints"""

    # Import and register blueprints here to avoid circular imports
    from app.routes.auth import bp as auth_bp
    from app.routes.chat import bp as chat_bp
    from app.routes.main import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(chat_bp, url_prefix='/api')


def register_error_handlers(app):
    """Register error handlers"""

    from flask import jsonify, request

    @app.errorhandler(400)
    def bad_request(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Bad request'}), 400
        return '<h1>400 Bad Request</h1><p>The request could not be understood by the server.</p>', 400

    @app.errorhandler(401)
    def unauthorized(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized'}), 401
        return '<h1>401 Unauthorized</h1><p>You need to log in to access this page.</p>', 401

    @app.errorhandler(403)
    def forbidden(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden'}), 403
        return '<h1>403 Forbidden</h1><p>You do not have permission to access this resource.</p>', 403

    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not found'}), 404
        return '<h1>404 Not Found</h1><p>The requested resource was not found.</p>', 404

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'Rate limit exceeded. Please slow down and try again later.',
                'code': 'RATE_LIMIT_EXCEEDED'
            }), 429
        return '<h1>429 Too Many Requests</h1><p>You have exceeded the rate limit. Please slow down and try again later.</p>', 429

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error(f'Internal server error: {error}')
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return '<h1>500 Internal Server Error</h1><p>An error occurred while processing your request.</p>', 500


def configure_logging(app):
    """Configure application logging"""

    if not app.debug and not app.testing:
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.mkdir('logs')

        # Set up file handler with rotation
        file_handler = RotatingFileHandler(
            app.config.get('LOG_FILE', 'logs/app.log'),
            maxBytes=10240000,  # 10MB
            backupCount=10
        )

        # Set logging format
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
        )
        file_handler.setFormatter(formatter)

        # Set log level
        log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'))
        file_handler.setLevel(log_level)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(log_level)

        app.logger.info('Application startup')
