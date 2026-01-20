"""
Simply AI - Home Edition
Compiled Application Entry Point

This script handles:
1. First-run setup (database initialization, migrations, admin creation)
2. Starting the Flask server
"""

import os
import sys
import webbrowser
import threading
import time
import secrets

# Handle PyInstaller frozen environment
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    BASE_DIR = os.path.dirname(sys.executable)
    # Add the base directory to path for imports
    sys.path.insert(0, BASE_DIR)
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Set up environment for Home Edition (before any imports)
# Use 'development' config which doesn't require Redis
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('DB_TYPE', 'sqlite')
os.environ['SQLALCHEMY_ECHO'] = 'false'  # Disable SQL query logging

# Configure quiet logging for compiled app (reduce console noise)
import logging

# Set root logger to only show warnings and above
logging.basicConfig(level=logging.WARNING, format='%(message)s')

# Suppress verbose output from various libraries
logging.getLogger('werkzeug').setLevel(logging.ERROR)  # Only show errors, not requests
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine.Engine').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
logging.getLogger('transformers').setLevel(logging.WARNING)
logging.getLogger('chromadb').setLevel(logging.WARNING)
logging.getLogger('chromadb.telemetry').setLevel(logging.WARNING)
logging.getLogger('filelock').setLevel(logging.WARNING)
logging.getLogger('PIL').setLevel(logging.WARNING)
logging.getLogger('google').setLevel(logging.WARNING)

# Generate a stable SECRET_KEY if not set (stored in .env file)
def ensure_secret_key():
    """Ensure a SECRET_KEY exists, generating one if needed."""
    env_file = os.path.join(BASE_DIR, '.env')

    # Check if SECRET_KEY already set in environment
    if os.environ.get('SECRET_KEY'):
        return

    # Check if .env file exists and has SECRET_KEY
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            content = f.read()
            if 'SECRET_KEY=' in content:
                # Load it
                for line in content.split('\n'):
                    if line.startswith('SECRET_KEY='):
                        os.environ['SECRET_KEY'] = line.split('=', 1)[1].strip()
                        return

    # Generate new SECRET_KEY and save to .env
    secret_key = secrets.token_hex(32)
    os.environ['SECRET_KEY'] = secret_key

    # Append to or create .env file
    with open(env_file, 'a') as f:
        f.write(f'\nSECRET_KEY={secret_key}\n')

ensure_secret_key()


def get_data_dir():
    """Get the data directory for the application."""
    # Use a 'data' subdirectory in the application folder
    data_dir = os.path.join(BASE_DIR, 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_instance_dir():
    """Get the instance directory for database."""
    instance_dir = os.path.join(BASE_DIR, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    return instance_dir


def is_first_run():
    """Check if this is the first run (no database exists)."""
    db_path = os.path.join(get_instance_dir(), 'simplyai.db')
    return not os.path.exists(db_path)


def run_first_time_setup():
    """Run first-time setup: initialize database, run migrations, create admin."""
    print()
    print("=" * 60)
    print("  Simply AI - Home Edition")
    print("  First-Time Setup")
    print("=" * 60)
    print()

    # Set environment variables for the app
    # Use 'development' config for Home Edition (no Redis required)
    os.environ['FLASK_ENV'] = 'development'
    os.environ['INSTANCE_PATH'] = get_instance_dir()

    # Import app components
    from app import create_app, db
    from app.models.rbac import Role, Permission
    from app.models.user import User
    # Import all models to ensure they're registered with SQLAlchemy
    from app.models import (
        Chat, Message, Attachment, PasswordHistory, TwoFABackupCode,
        Pending2FAVerification, UserSettings, ModelVisibility,
        AdminSettings, Document, DocumentChunk
    )

    app = create_app('development')

    with app.app_context():
        # Step 1: Create database tables
        print("[1/4] Creating database tables...")
        db.create_all()
        print("      Done!")

        # Step 2: Initialize roles and permissions
        print("[2/4] Initializing roles and permissions...")
        Role.initialize_system_roles()
        Permission.initialize_system_permissions()
        Permission.assign_default_permissions_to_roles()
        print("      Done!")

        # Step 3: Run migrations (add columns/settings)
        print("[3/4] Applying database migrations...")
        run_migrations(app)
        print("      Done!")

        # Step 4: Create admin user
        print("[4/4] Creating administrator account...")
        admin_result = create_default_admin(app, db, User, Role)
        print("      Done!")

    print()
    print("=" * 60)
    print("  Setup Complete!")
    print("=" * 60)
    print()

    if admin_result == 'installer':
        print("  Administrator account created with your chosen credentials.")
        print()
        print("  You can now log in with the username and password")
        print("  you configured during installation.")
    elif admin_result == 'default':
        print("  Default Administrator Credentials:")
        print("  -----------------------------------")
        print("  Username: admin")
        print("  Password: AdminPass123!@#")
        print()
        print("  IMPORTANT: Change this password after first login!")
    else:
        # admin_result == 'skipped' - users already exist
        print("  Using existing administrator account.")

    print()
    print("=" * 60)
    print()


def run_migrations(app):
    """Run database migrations."""
    from app import db
    from app.models.admin_settings import AdminSettings
    from app.models.model_visibility import ModelVisibility

    with app.app_context():
        # Migration 1: Initialize model visibility (populates the model dropdown)
        try:
            existing_models = ModelVisibility.query.first()
            if not existing_models:
                print("      - Initializing model visibility...")
                ModelVisibility.initialize_default_models()
                print("        Models initialized successfully")
        except Exception as e:
            print(f"      Note: Model visibility migration: {e}")
            db.session.rollback()

        # Migration 2: Initialize admin settings using the proper method
        try:
            existing_settings = AdminSettings.query.first()
            if not existing_settings:
                print("      - Initializing admin settings...")
                AdminSettings.initialize_default_settings()
                print("        Admin settings initialized successfully")

            # Add additional settings that might be missing
            # Keep these in sync with scripts/migrations/ and static/js/settings.js
            additional_settings = [
                ('rag_enabled', 'true', 'boolean', 'Enable RAG (Retrieval-Augmented Generation)'),
                ('rag_default_chunk_size', '512', 'integer', 'Default chunk size for RAG documents'),
                ('rag_default_overlap', '50', 'integer', 'Default overlap for RAG chunks'),
                ('rag_default_top_k', '5', 'integer', 'Default number of chunks to retrieve'),
                ('rag_embedding_model', 'auto', 'string', 'Embedding model provider'),
                ('rag_max_documents_per_user', '50', 'integer', 'Max documents per user'),
                ('child_safety_enabled', 'true', 'boolean', 'Enable age-based content safety'),
                ('child_system_prompt', '''You are a helpful, friendly AI assistant talking with a child under 12 years old.
Please follow these guidelines:
- Use simple, age-appropriate language
- Never discuss violence, adult themes, or scary content
- Encourage learning and creativity
- Be patient and supportive
- If asked about inappropriate topics, gently redirect to child-friendly subjects
- Never collect personal information or encourage sharing private details
- Promote safety and responsible behaviour''', 'string', 'System prompt for users under 12'),
                ('teen_system_prompt', '''You are a helpful AI assistant talking with a teenager (12-17 years old).
Please follow these guidelines:
- Be informative while maintaining age-appropriate boundaries
- Avoid explicit content, violence, or harmful advice
- Encourage critical thinking and learning
- If asked about sensitive topics, provide balanced, educational responses
- Never encourage dangerous activities or substance use
- Support mental health and recommend professional help when appropriate
- Protect user privacy and personal information''', 'string', 'System prompt for teens 12-17'),
                # Model ID settings - keep in sync with AdminSettings.DEFAULT_MODEL_IDS
                ('system_model_id_gemini', 'gemini-3-flash-preview', 'string', 'System model ID for Google Gemini'),
                ('system_model_id_openai', 'gpt-5-mini-2025-08-07', 'string', 'System model ID for OpenAI ChatGPT'),
                ('system_model_id_anthropic', 'claude-haiku-4-5-20251001', 'string', 'System model ID for Anthropic Claude'),
                ('system_model_id_xai', 'grok-4-1-fast-non-reasoning-latest', 'string', 'System model ID for xAI Grok'),
                ('system_model_id_lm_studio', '', 'string', 'System model ID for LM Studio'),
                ('system_model_id_ollama', '', 'string', 'System model ID for Ollama'),
                ('system_model_url_lm_studio', 'http://localhost:1234/v1/chat/completions', 'string', 'System URL for LM Studio server'),
                ('system_model_url_ollama', 'http://localhost:11434/api/chat', 'string', 'System URL for Ollama server'),
            ]
            for setting_key, setting_value, setting_type, description in additional_settings:
                existing = AdminSettings.query.filter_by(setting_key=setting_key).first()
                if not existing:
                    setting = AdminSettings(
                        setting_key=setting_key,
                        setting_value=setting_value,
                        setting_type=setting_type,
                        description=description
                    )
                    db.session.add(setting)
            db.session.commit()
            print("        Additional settings configured")
        except Exception as e:
            print(f"      Note: Admin settings migration: {e}")
            db.session.rollback()


def get_installer_config():
    """Check for installer-provided admin credentials."""
    config_path = os.path.join(BASE_DIR, 'first_run_config.json')
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config, config_path
        except Exception as e:
            print(f"      Warning: Could not read installer config: {e}")
    return None, None


def secure_delete_file(filepath):
    """Securely delete a file by overwriting before removal."""
    try:
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            with open(filepath, 'wb') as f:
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(f.fileno())
            os.remove(filepath)
            return True
    except Exception:
        try:
            os.remove(filepath)
            return True
        except:
            pass
    return False


def create_default_admin(app, db, User, Role):
    """
    Create the admin user (from installer config or defaults).

    Returns:
        'installer' - Admin created with installer-provided credentials
        'default' - Admin created with default credentials
        'skipped' - No admin created (users already exist)
    """
    with app.app_context():
        # Check if any users already exist
        if User.query.count() > 0:
            print("      Users already exist, skipping admin creation.")
            # Clean up config file if it exists
            config, config_path = get_installer_config()
            if config_path:
                secure_delete_file(config_path)
            return 'skipped'

        # Check for installer-provided credentials
        config, config_path = get_installer_config()

        if config:
            # Use installer-provided credentials
            username = config.get('admin_username', 'admin')
            email = config.get('admin_email', 'admin@localhost')
            password = config.get('admin_password')

            if not password:
                print("      Warning: No password in installer config, using default")
                password = 'AdminPass123!@#'
                using_installer_creds = False
            else:
                using_installer_creds = True
                print(f"      Using installer-configured credentials for '{username}'")
        else:
            # Use default credentials
            username = 'admin'
            email = 'admin@localhost'
            password = 'AdminPass123!@#'
            using_installer_creds = False

        # Check if username already exists
        existing = User.query.filter_by(username=username).first()
        if existing:
            print(f"      User '{username}' already exists.")
            if config_path:
                secure_delete_file(config_path)
            return 'skipped'

        # Create admin user
        user = User(
            username=username,
            email=email,
            is_admin=True
        )

        success, error = user.set_password(password, check_history=False)
        if not success:
            print(f"      Warning: {error}")
            if config_path:
                secure_delete_file(config_path)
            return 'skipped'

        db.session.add(user)
        db.session.flush()

        # Assign roles
        super_admin_role = Role.query.filter_by(name='super_admin').first()
        user_role = Role.query.filter_by(name='user').first()

        if super_admin_role:
            user.add_role(super_admin_role)
        if user_role:
            user.add_role(user_role)

        db.session.commit()

        # Securely delete the config file
        if config_path:
            if secure_delete_file(config_path):
                print("      Installer config securely deleted.")

        # Return which type of credentials were used
        return 'installer' if using_installer_creds else 'default'


def open_browser(port):
    """Open the default browser after a short delay."""
    time.sleep(2)
    webbrowser.open(f'http://localhost:{port}')


def main():
    """Main entry point."""
    # Ensure required directories exist
    get_data_dir()
    get_instance_dir()
    os.makedirs(os.path.join(BASE_DIR, 'uploads', 'images'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'uploads', 'documents'), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

    # Check for first run
    if is_first_run():
        run_first_time_setup()

    # Use development config for Home Edition (no Redis required, memory rate limiting)
    os.environ['FLASK_ENV'] = 'development'

    # Get port from environment or use default
    port = int(os.environ.get('PORT', 8080))

    print()
    print("=" * 60)
    print("  Simply AI - Home Edition")
    print("=" * 60)
    print()
    print(f"  Starting server on http://localhost:{port}")
    print()
    print("  Press Ctrl+C to stop the server")
    print()
    print("=" * 60)
    print()

    # Open browser in background thread
    browser_thread = threading.Thread(target=open_browser, args=(port,))
    browser_thread.daemon = True
    browser_thread.start()

    # Create and run the Flask app
    from app import create_app
    app = create_app('development')

    # Run the server
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
