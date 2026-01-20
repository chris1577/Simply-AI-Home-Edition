"""
Create Admin User Script

This script creates an admin user with super_admin role.

Usage:
    python create_admin.py
"""

import os
import sys
import getpass

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.user import User
from app.models.rbac import Role
from app.utils.validators import validate_username, validate_email, validate_password


def create_admin_user():
    """Create an admin user interactively"""

    app = create_app('development')

    with app.app_context():
        print("[CREATE ADMIN USER]")
        print("=" * 50)

        # Get username
        while True:
            username = input("\nEnter username: ").strip()
            valid, error = validate_username(username)

            if not valid:
                print(f"[ERROR] {error}")
                continue

            # Check if username exists
            if User.query.filter_by(username=username).first():
                print(f"[ERROR] Username '{username}' already exists")
                continue

            break

        # Get email
        while True:
            email = input("Enter email: ").strip()
            valid, error = validate_email(email)

            if not valid:
                print(f"[ERROR] {error}")
                continue

            # Check if email exists
            if User.query.filter_by(email=email).first():
                print(f"[ERROR] Email '{email}' already exists")
                continue

            break

        # Get password
        while True:
            password = getpass.getpass("Enter password (min 12 chars): ")
            password_confirm = getpass.getpass("Confirm password: ")

            if password != password_confirm:
                print("[ERROR] Passwords do not match")
                continue

            valid, errors = validate_password(password)

            if not valid:
                print("[ERROR] Password does not meet requirements:")
                for err in errors:
                    print(f"   - {err}")
                continue

            break

        # Create user
        print("\n[WORKING] Creating admin user...")
        user = User(username=username, email=email, is_admin=True)
        success, error = user.set_password(password, check_history=False)

        if not success:
            print(f"[ERROR] Error setting password: {error}")
            return

        # Add user to session first (important for relationship operations)
        db.session.add(user)
        db.session.flush()  # Flush to get the user ID

        # Add super_admin role
        super_admin_role = Role.query.filter_by(name='super_admin').first()

        if not super_admin_role:
            print("[ERROR] Super admin role not found. Please run init_db.py first.")
            return

        user.add_role(super_admin_role)

        # Add user role as well
        user_role = Role.query.filter_by(name='user').first()
        if user_role:
            user.add_role(user_role)

        db.session.commit()

        print("\n[OK] Admin user created successfully!")
        print(f"\n   Username: {username}")
        print(f"   Email: {email}")
        print(f"   Roles: {', '.join([role.name for role in user.roles])}")
        print(f"   User ID: {user.id}")

        print("\n[NEXT] Next steps:")
        print("   1. Start the server: python run.py")
        print("   2. Login at: http://localhost:5000")
        print("   3. Or test API: POST /auth/login")


if __name__ == '__main__':
    try:
        create_admin_user()
    except KeyboardInterrupt:
        print("\n\n[ERROR] Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error creating admin user: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
