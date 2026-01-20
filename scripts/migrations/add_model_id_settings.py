"""
Database migration script to add system model ID settings.

This script adds default model ID settings to the admin_settings table,
allowing super admins to configure model IDs through the Settings page
instead of environment variables.

Run this script to update your database:
    python add_model_id_settings.py
"""

import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.admin_settings import AdminSettings


def add_model_id_settings():
    """Add default model ID settings to admin_settings table"""

    app = create_app('development')

    with app.app_context():
        print("Adding system model ID settings to admin_settings table...")

        # Default model IDs for cloud providers
        # Keep these in sync with:
        # - app/models/admin_settings.py (DEFAULT_MODEL_IDS)
        # - run_compiled.py (run_migrations function)
        model_settings = [
            {
                'setting_key': 'system_model_id_gemini',
                'setting_value': 'gemini-3-flash-preview',
                'setting_type': 'string',
                'description': 'System model ID for Google Gemini'
            },
            {
                'setting_key': 'system_model_id_openai',
                'setting_value': 'gpt-5-mini-2025-08-07',
                'setting_type': 'string',
                'description': 'System model ID for OpenAI ChatGPT'
            },
            {
                'setting_key': 'system_model_id_anthropic',
                'setting_value': 'claude-haiku-4-5-20251001',
                'setting_type': 'string',
                'description': 'System model ID for Anthropic Claude'
            },
            {
                'setting_key': 'system_model_id_xai',
                'setting_value': 'grok-4-1-fast-non-reasoning-latest',
                'setting_type': 'string',
                'description': 'System model ID for xAI Grok'
            },
            # Local model IDs (default empty, users configure these)
            {
                'setting_key': 'system_model_id_lm_studio',
                'setting_value': '',
                'setting_type': 'string',
                'description': 'System model ID for LM Studio'
            },
            {
                'setting_key': 'system_model_id_ollama',
                'setting_value': '',
                'setting_type': 'string',
                'description': 'System model ID for Ollama'
            },
            # Local model URLs
            {
                'setting_key': 'system_model_url_lm_studio',
                'setting_value': 'http://localhost:1234/v1/chat/completions',
                'setting_type': 'string',
                'description': 'System URL for LM Studio server'
            },
            {
                'setting_key': 'system_model_url_ollama',
                'setting_value': 'http://localhost:11434/api/chat',
                'setting_type': 'string',
                'description': 'System URL for Ollama server'
            }
        ]

        try:
            added_count = 0
            skipped_count = 0

            for setting_data in model_settings:
                existing = AdminSettings.query.filter_by(
                    setting_key=setting_data['setting_key']
                ).first()

                if not existing:
                    setting = AdminSettings(**setting_data)
                    db.session.add(setting)
                    added_count += 1
                    print(f"  [+] Added: {setting_data['setting_key']} = {setting_data['setting_value'] or '(empty)'}")
                else:
                    skipped_count += 1
                    print(f"  [=] Exists: {setting_data['setting_key']} = {existing.setting_value or '(empty)'}")

            db.session.commit()

            print(f"\n[OK] Migration completed!")
            print(f"     Added: {added_count} settings")
            print(f"     Skipped (already exist): {skipped_count} settings")

            print("\nNote: Model IDs are now configured through the Settings page (super_admin only).")
            print("      You can safely remove model ID environment variables from your .env file.")

        except Exception as e:
            print(f"\n[ERROR] Error during migration: {str(e)}")
            db.session.rollback()
            raise


if __name__ == '__main__':
    add_model_id_settings()
