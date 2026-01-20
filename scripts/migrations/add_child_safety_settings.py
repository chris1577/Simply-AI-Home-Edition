"""
Migration script to add child safety system prompt settings.
These settings enable age-based content filtering for child and teen users.

Usage: python scripts/migrations/add_child_safety_settings.py
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.admin_settings import AdminSettings


def add_child_safety_settings():
    """Add child safety system prompt settings to admin_settings"""
    app = create_app('development')

    with app.app_context():
        print("Adding child safety settings...")

        # Keep these prompts in sync with:
        # - static/js/settings.js (DEFAULT_CHILD_PROMPT, DEFAULT_TEEN_PROMPT)
        # - run_compiled.py (run_migrations function)
        child_safety_settings = [
            {
                'setting_key': 'child_safety_enabled',
                'setting_value': 'true',
                'setting_type': 'boolean',
                'description': 'Enable age-based safety prompts for child and teen users'
            },
            {
                'setting_key': 'child_system_prompt',
                'setting_value': '''You are a helpful, friendly AI assistant talking with a child under 12 years old.
Please follow these guidelines:
- Use simple, age-appropriate language
- Never discuss violence, adult themes, or scary content
- Encourage learning and creativity
- Be patient and supportive
- If asked about inappropriate topics, gently redirect to child-friendly subjects
- Never collect personal information or encourage sharing private details
- Promote safety and responsible behaviour''',
                'setting_type': 'string',
                'description': 'System prompt prepended for users under 12 years old'
            },
            {
                'setting_key': 'teen_system_prompt',
                'setting_value': '''You are a helpful AI assistant talking with a teenager (12-17 years old).
Please follow these guidelines:
- Be informative while maintaining age-appropriate boundaries
- Avoid explicit content, violence, or harmful advice
- Encourage critical thinking and learning
- If asked about sensitive topics, provide balanced, educational responses
- Never encourage dangerous activities or substance use
- Support mental health and recommend professional help when appropriate
- Protect user privacy and personal information''',
                'setting_type': 'string',
                'description': 'System prompt prepended for users aged 12-17'
            }
        ]

        added_count = 0
        skipped_count = 0

        for setting in child_safety_settings:
            existing = AdminSettings.query.filter_by(setting_key=setting['setting_key']).first()
            if not existing:
                new_setting = AdminSettings(**setting)
                db.session.add(new_setting)
                print(f"  [+] Added: {setting['setting_key']}")
                added_count += 1
            else:
                print(f"  [=] Exists: {setting['setting_key']}")
                skipped_count += 1

        db.session.commit()
        print(f"\n[OK] Child safety settings migration complete!")
        print(f"     Added: {added_count}, Skipped: {skipped_count}")


if __name__ == '__main__':
    print("=" * 60)
    print("Migration: Add child safety system prompt settings")
    print("=" * 60)
    add_child_safety_settings()
