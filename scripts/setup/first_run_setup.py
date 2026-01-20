"""
First Run Setup Script

This script is called on application startup to check for and process
first-run configuration (admin credentials set during installation).

The installer creates a first_run_config.json file with admin credentials.
This script reads that file, creates the admin user, and then securely
deletes the config file.

Usage:
    Called automatically from run.py on startup
    Can also be run manually: python first_run_setup.py
"""

import json
import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


def get_config_path():
    """Get the path to the first-run config file"""
    # Check in the application root directory
    return os.path.join(project_root, 'first_run_config.json')


def secure_delete_file(filepath):
    """Securely delete a file by overwriting before removal"""
    try:
        if os.path.exists(filepath):
            # Overwrite with random data before deleting
            file_size = os.path.getsize(filepath)
            with open(filepath, 'wb') as f:
                f.write(os.urandom(file_size))
                f.flush()
                os.fsync(f.fileno())
            os.remove(filepath)
            return True
    except Exception as e:
        # If secure delete fails, try normal delete
        try:
            os.remove(filepath)
            return True
        except:
            print(f"[WARNING] Could not delete config file: {e}")
            return False
    return False


def process_first_run_config(app=None):
    """
    Check for first-run config and create admin user if found.

    Args:
        app: Flask application instance (optional, will create if not provided)

    Returns:
        tuple: (success: bool, message: str)
    """
    config_path = get_config_path()

    # Check if config file exists
    if not os.path.exists(config_path):
        return True, "No first-run config found (normal operation)"

    print("[SETUP] First-run configuration detected...")

    # Read the config file
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        secure_delete_file(config_path)
        return False, f"Invalid config file format: {e}"
    except Exception as e:
        return False, f"Error reading config file: {e}"

    # Validate required fields
    required_fields = ['admin_username', 'admin_email', 'admin_password']
    for field in required_fields:
        if field not in config or not config[field]:
            secure_delete_file(config_path)
            return False, f"Missing required field: {field}"

    username = config['admin_username']
    email = config['admin_email']
    password = config['admin_password']

    # Create Flask app context if not provided
    if app is None:
        from app import create_app
        app = create_app(os.environ.get('FLASK_ENV', 'production'))

    with app.app_context():
        from app import db
        from app.models.user import User
        from app.models.rbac import Role, Permission

        # Initialize database tables if they don't exist
        db.create_all()

        # Initialize roles and permissions if they don't exist
        if Role.query.count() == 0:
            print("[SETUP] Initializing roles...")
            Role.initialize_system_roles()

        if Permission.query.count() == 0:
            print("[SETUP] Initializing permissions...")
            Permission.initialize_system_permissions()
            Permission.assign_default_permissions_to_roles()

        # Check if any users already exist
        if User.query.count() > 0:
            print("[SETUP] Users already exist, skipping admin creation")
            secure_delete_file(config_path)
            return True, "Users already exist, config file removed"

        # Check if username already exists (shouldn't happen on first run)
        if User.query.filter_by(username=username).first():
            secure_delete_file(config_path)
            return False, f"Username '{username}' already exists"

        # Check if email already exists
        if User.query.filter_by(email=email).first():
            secure_delete_file(config_path)
            return False, f"Email '{email}' already exists"

        # Create admin user
        print(f"[SETUP] Creating admin user '{username}'...")
        user = User(
            username=username,
            email=email,
            is_admin=True
        )

        # Set password (skip history check for first user)
        success, error = user.set_password(password, check_history=False)
        if not success:
            secure_delete_file(config_path)
            return False, f"Password error: {error}"

        # Add user to session
        db.session.add(user)
        db.session.flush()

        # Assign super_admin role
        super_admin_role = Role.query.filter_by(name='super_admin').first()
        if super_admin_role:
            user.add_role(super_admin_role)
        else:
            print("[WARNING] super_admin role not found")

        # Also assign user role
        user_role = Role.query.filter_by(name='user').first()
        if user_role:
            user.add_role(user_role)

        db.session.commit()

        print(f"[SETUP] Admin user created successfully!")
        print(f"        Username: {username}")
        print(f"        Email: {email}")

        # Securely delete the config file
        if secure_delete_file(config_path):
            print("[SETUP] Configuration file securely deleted")
        else:
            print("[WARNING] Could not delete configuration file")

        return True, f"Admin user '{username}' created successfully"


def run_first_run_setup():
    """Main entry point for first-run setup"""
    success, message = process_first_run_config()

    if success:
        if "No first-run config" not in message:
            print(f"[OK] {message}")
    else:
        print(f"[ERROR] {message}")
        return False

    return True


if __name__ == '__main__':
    try:
        success = run_first_run_setup()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n[CANCELLED] Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
