"""
Database migration script to add vision capability settings for local models.

This script adds the lm_studio_vision_capable and ollama_vision_capable
settings to the admin_settings table, enabling vision/image support
for local LLM models when vision-capable models are loaded.

Run this script to update your database:
    python add_vision_settings.py
"""

import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.admin_settings import AdminSettings


def add_vision_settings():
    """Add vision capability settings for local models"""

    app = create_app('development')

    with app.app_context():
        print("Adding vision capability settings for local models...")

        try:
            # Define the new vision settings
            vision_settings = [
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

            # Add each setting if it doesn't exist
            for setting_data in vision_settings:
                existing = AdminSettings.query.filter_by(setting_key=setting_data['setting_key']).first()
                if not existing:
                    setting = AdminSettings(**setting_data)
                    db.session.add(setting)
                    print(f"  [+] Added setting: {setting_data['setting_key']}")
                else:
                    print(f"  [=] Setting already exists: {setting_data['setting_key']}")

            db.session.commit()
            print("\n[OK] Vision settings added successfully!")

            # Display current vision settings
            print("\nCurrent vision settings:")
            for key in ['lm_studio_vision_capable', 'ollama_vision_capable']:
                setting = AdminSettings.query.filter_by(setting_key=key).first()
                if setting:
                    print(f"  - {setting.setting_key}: {setting.get_typed_value()}")
                    print(f"    Description: {setting.description}")

            print("\nNote: Vision settings are enabled by default.")
            print("Super admin users can disable them from Admin Settings if needed.")
            print("Make sure to load vision-capable models in LM Studio or Ollama for vision to work.")

        except Exception as e:
            print(f"\n[ERROR] Error during migration: {str(e)}")
            db.session.rollback()
            raise


if __name__ == '__main__':
    add_vision_settings()
