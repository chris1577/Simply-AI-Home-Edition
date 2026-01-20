"""
Reset SQL Server Express Database

This script:
1. Drops the existing simplyai database (if exists)
2. Creates a fresh simplyai database
3. Creates all tables
4. Initializes default data (roles, permissions, model visibility, admin settings)
5. Creates default admin user

Usage:
    python scripts/setup/reset_sqlexpress.py
    Or: bat\reset_sqlexpress.bat
"""

import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
os.chdir(project_root)

import pyodbc


def get_master_connection():
    """Connect to master database to manage databases"""
    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost\\SQLEXPRESS;"
        "DATABASE=master;"
        "Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str, autocommit=True)


def reset_database():
    """Drop and recreate the simplyai database"""
    print("=" * 60)
    print("SQL Server Express Database Reset")
    print("=" * 60)
    print()

    db_name = "simplyai"

    # Step 1: Connect to master and drop/create database
    print(f"[1/5] Connecting to SQL Server Express...")
    try:
        conn = get_master_connection()
        cursor = conn.cursor()
        print("      Connected to master database")
    except Exception as e:
        print(f"      ERROR: Could not connect to SQL Server Express")
        print(f"      {e}")
        print()
        print("      Make sure:")
        print("      - SQL Server Express is running")
        print("      - ODBC Driver 17 for SQL Server is installed")
        return False

    # Step 2: Drop existing database
    print(f"[2/5] Dropping existing '{db_name}' database (if exists)...")
    try:
        # Kill existing connections
        cursor.execute(f"""
            IF EXISTS (SELECT name FROM sys.databases WHERE name = '{db_name}')
            BEGIN
                ALTER DATABASE [{db_name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
                DROP DATABASE [{db_name}];
            END
        """)
        print(f"      Database dropped (or didn't exist)")
    except Exception as e:
        print(f"      Warning: {e}")

    # Step 3: Create new database
    print(f"[3/5] Creating fresh '{db_name}' database...")
    try:
        cursor.execute(f"CREATE DATABASE [{db_name}]")
        print(f"      Database created successfully")
    except Exception as e:
        print(f"      ERROR: Could not create database: {e}")
        return False

    cursor.close()
    conn.close()

    # Step 4: Create tables using Flask app context
    print("[4/5] Creating database tables...")
    try:
        # Import here to avoid loading before DB exists
        from app import create_app, db
        from app.models.rbac import Role, Permission
        from app.models.model_visibility import ModelVisibility
        from app.models.admin_settings import AdminSettings

        app = create_app()
        with app.app_context():
            # Create all tables
            db.create_all()
            print("      All tables created")

            # Initialize roles
            print("      Initializing roles...")
            Role.initialize_system_roles()

            # Initialize permissions
            print("      Initializing permissions...")
            Permission.initialize_system_permissions()

            # Initialize model visibility
            print("      Initializing model visibility...")
            ModelVisibility.initialize_default_models()

            # Initialize admin settings
            print("      Initializing admin settings...")
            AdminSettings.initialize_default_settings()

            db.session.commit()
            print("      Default data initialized")

    except Exception as e:
        print(f"      ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 5: Create admin user
    print("[5/5] Creating admin user...")
    try:
        from app.models.user import User

        with app.app_context():
            # Check if admin exists
            existing = User.query.filter_by(username='admin').first()
            if existing:
                print("      Admin user already exists")
            else:
                admin = User(
                    username='admin',
                    email='admin@simply.ai',
                    is_active=True,
                    is_admin=True
                )
                admin.set_password('AdminPass123!@#')
                db.session.add(admin)
                db.session.commit()

                # Assign roles (need to fetch Role objects)
                super_admin_role = Role.query.filter_by(name='super_admin').first()
                user_role = Role.query.filter_by(name='user').first()

                if super_admin_role:
                    admin.add_role(super_admin_role)
                if user_role:
                    admin.add_role(user_role)
                db.session.commit()

                print("      Admin user created")
                print()
                print("      Credentials:")
                print("      Username: admin")
                print("      Password: AdminPass123!@#")

    except Exception as e:
        print(f"      ERROR: {e}")
        return False

    print()
    print("=" * 60)
    print("DATABASE RESET COMPLETE")
    print("=" * 60)
    print()
    print("You can now start the server with: python run.py")
    print()

    return True


if __name__ == '__main__':
    # Check for --no-confirm or -y flag
    no_confirm = '--no-confirm' in sys.argv or '-y' in sys.argv

    if no_confirm:
        print()
        success = reset_database()
        sys.exit(0 if success else 1)
    else:
        # Confirm before proceeding
        print()
        response = input("This will DELETE all data in the simplyai database. Continue? (yes/no): ")
        print()

        if response.lower() in ['yes', 'y']:
            success = reset_database()
            sys.exit(0 if success else 1)
        else:
            print("Reset cancelled.")
            sys.exit(0)
