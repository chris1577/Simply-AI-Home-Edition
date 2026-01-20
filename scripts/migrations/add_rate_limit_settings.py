"""
Migration script to add rate limit settings.
These settings allow admins to customize rate limits for various endpoints.

Usage: python scripts/migrations/add_rate_limit_settings.py
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.admin_settings import AdminSettings


def add_rate_limit_settings():
    """Add rate limit settings to admin_settings"""
    app = create_app('development')

    with app.app_context():
        print("Adding rate limit settings...")

        # Keep these defaults in sync with:
        # - app/models/admin_settings.py (DEFAULT_RATE_LIMITS)
        # - static/js/settings.js (rate limit defaults)
        # - app/__init__.py (limiter configuration)
        rate_limit_settings = [
            {
                'setting_key': 'rate_limit_enabled',
                'setting_value': 'true',
                'setting_type': 'boolean',
                'description': 'Enable rate limiting for all endpoints'
            },
            {
                'setting_key': 'rate_limit_chat',
                'setting_value': '100',
                'setting_type': 'integer',
                'description': 'Maximum chat requests per hour'
            },
            {
                'setting_key': 'rate_limit_attachment_upload',
                'setting_value': '50',
                'setting_type': 'integer',
                'description': 'Maximum attachment uploads per hour'
            },
            {
                'setting_key': 'rate_limit_document_upload',
                'setting_value': '20',
                'setting_type': 'integer',
                'description': 'Maximum document uploads per hour (RAG)'
            },
            {
                'setting_key': 'rate_limit_improve_prompt',
                'setting_value': '30',
                'setting_type': 'integer',
                'description': 'Maximum prompt improvement requests per hour'
            },
            {
                'setting_key': 'rate_limit_login',
                'setting_value': '10',
                'setting_type': 'integer',
                'description': 'Maximum login attempts per minute'
            },
            {
                'setting_key': 'rate_limit_register',
                'setting_value': '5',
                'setting_type': 'integer',
                'description': 'Maximum registration attempts per hour'
            },
            {
                'setting_key': 'rate_limit_2fa',
                'setting_value': '10',
                'setting_type': 'integer',
                'description': 'Maximum 2FA verification attempts per minute'
            }
        ]

        added_count = 0
        skipped_count = 0

        for setting in rate_limit_settings:
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
        print(f"\n[OK] Rate limit settings migration complete!")
        print(f"     Added: {added_count}, Skipped: {skipped_count}")


if __name__ == '__main__':
    print("=" * 60)
    print("Migration: Add rate limit settings")
    print("=" * 60)
    add_rate_limit_settings()
