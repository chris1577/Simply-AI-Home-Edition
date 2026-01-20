from app.routes.main import bp as main_bp
from app.routes.auth import bp as auth_bp
from app.routes.chat import bp as chat_bp

__all__ = ['main_bp', 'auth_bp', 'chat_bp']
