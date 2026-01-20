"""
Migration script to add distilled context feature.
Adds admin setting toggle and distilled_content column to messages table.

The distilled context feature automatically summarizes messages to enable
longer conversations without hitting context limits.

Usage: python scripts/migrations/add_distilled_context.py
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.admin_settings import AdminSettings
from sqlalchemy import text


def add_distilled_context_setting():
    """Add distilled context admin setting"""
    print("\n[1/2] Adding distilled context admin setting...")

    settings = [
        {
            'setting_key': 'distilled_context_enabled',
            'setting_value': 'false',
            'setting_type': 'boolean',
            'description': 'Enable distilled context for longer conversations. When enabled, messages are automatically summarized and summaries are used as context instead of full messages.'
        }
    ]

    added_count = 0
    skipped_count = 0

    for setting in settings:
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
    print(f"     Added: {added_count}, Skipped: {skipped_count}")


def add_distilled_content_column():
    """Add distilled_content column to messages table"""
    print("\n[2/2] Adding distilled_content column to messages table...")

    try:
        # Check if column already exists
        inspector = db.inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('messages')]

        dialect = db.engine.dialect.name

        if 'distilled_content' not in existing_columns:
            print("  Adding column: distilled_content")
            if dialect == 'mssql':
                db.session.execute(text('ALTER TABLE messages ADD distilled_content NVARCHAR(MAX) NULL'))
            else:
                db.session.execute(text('ALTER TABLE messages ADD COLUMN distilled_content TEXT'))
            db.session.commit()
            print("  [+] distilled_content column added!")
        else:
            print("  [=] distilled_content column already exists, skipping...")

    except Exception as e:
        db.session.rollback()
        print(f"  [ERROR] Error adding column: {str(e)}")
        raise


def run_migration():
    """Run the full migration"""
    app = create_app('development')

    with app.app_context():
        add_distilled_context_setting()
        add_distilled_content_column()


if __name__ == '__main__':
    print("=" * 60)
    print("Migration: Add distilled context feature")
    print("=" * 60)
    run_migration()
    print("\n" + "=" * 60)
    print("[OK] Distilled context migration complete!")
    print("=" * 60)
