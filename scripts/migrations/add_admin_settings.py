"""
Database migration script to add admin_settings table.

This script adds the admin_settings table for storing application-wide
admin configuration settings, starting with the sensitive information filter.

Run this script to update your database:
    python add_admin_settings.py
"""

import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.admin_settings import AdminSettings

def add_admin_settings_table():
    """Create admin_settings table and initialize default settings"""

    app = create_app('development')

    with app.app_context():
        print("Creating admin_settings table...")

        try:
            # Create the table
            db.create_all()
            print("[OK] admin_settings table created successfully")

            # Initialize default settings
            print("\nInitializing default admin settings...")
            AdminSettings.initialize_default_settings()
            print("[OK] Default settings initialized")

            # Display current settings
            print("\nCurrent admin settings:")
            settings = AdminSettings.query.all()
            for setting in settings:
                print(f"  - {setting.setting_key}: {setting.get_typed_value()} ({setting.setting_type})")
                print(f"    Description: {setting.description}")

            print("\n[OK] Migration completed successfully!")
            print("\nNote: The sensitive information filter is enabled by default.")
            print("Super admin users can disable it from Admin Settings in the app if needed.")

        except Exception as e:
            print(f"\n[ERROR] Error during migration: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    add_admin_settings_table()
