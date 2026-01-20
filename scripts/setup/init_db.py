"""
Database Initialization Script

This script initializes the database with all required tables and
sets up the Role-Based Access Control (RBAC) system with default roles and permissions.

Run this script once after setting up the application:
    python init_db.py
"""

import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.rbac import Role, Permission
from app.models.user import User
# Import all models to ensure they're registered with SQLAlchemy
from app.models import *  # noqa


def init_database():
    """Initialize the database with tables, roles, and permissions"""

    app = create_app('development')

    with app.app_context():
        print("[DATABASE] Initializing database...")

        # Create all tables
        print("   [TABLES] Creating database tables...")
        db.create_all()
        print("   [OK] Database tables created successfully")

        # Initialize roles
        print("\n   [ROLES] Initializing roles...")
        Role.initialize_system_roles()
        roles = Role.query.all()
        print(f"   [OK] Created {len(roles)} roles:")
        for role in roles:
            print(f"      - {role.name} (level {role.level})")

        # Initialize permissions
        print("\n   [PERMISSIONS] Initializing permissions...")
        Permission.initialize_system_permissions()
        permissions = Permission.query.all()
        print(f"   [OK] Created {len(permissions)} permissions:")
        for perm in permissions:
            print(f"      - {perm.name} ({perm.resource}.{perm.action})")

        # Assign permissions to roles
        print("\n   [RBAC] Assigning permissions to roles...")
        Permission.assign_default_permissions_to_roles()
        print("   [OK] Permissions assigned successfully")

        # Check if any users exist
        user_count = User.query.count()
        print(f"\n   [USERS] Current users in database: {user_count}")

        if user_count == 0:
            print("\n   [TIP] Create your first admin user with:")
            print("      python create_admin.py")

        print("\n[SUCCESS] Database initialization complete!")
        print("\n[NEXT STEPS]")
        print("   1. Create an admin user (python create_admin.py)")
        print("   2. Start the server (python run.py or start_server.bat)")
        print("   3. Test the API endpoints")


if __name__ == '__main__':
    try:
        init_database()
    except Exception as e:
        print(f"\n[ERROR] Error during database initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
