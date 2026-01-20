"""
Migration script to add token tracking columns to messages table.
Adds input_tokens and output_tokens for tracking AI API token usage.

Usage: python scripts/migrations/add_token_tracking.py
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from sqlalchemy import text


def add_token_tracking():
    """Add input_tokens and output_tokens columns to messages table"""
    app = create_app('development')

    with app.app_context():
        try:
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('messages')]

            dialect = db.engine.dialect.name

            # Add input_tokens column
            if 'input_tokens' not in existing_columns:
                print("Adding column: input_tokens")
                if dialect == 'mssql':
                    db.session.execute(text('ALTER TABLE messages ADD input_tokens INT DEFAULT 0'))
                else:
                    db.session.execute(text('ALTER TABLE messages ADD COLUMN input_tokens INTEGER DEFAULT 0'))
                print("[OK] input_tokens column added!")
            else:
                print("[=] input_tokens column already exists, skipping...")

            # Add output_tokens column
            if 'output_tokens' not in existing_columns:
                print("Adding column: output_tokens")
                if dialect == 'mssql':
                    db.session.execute(text('ALTER TABLE messages ADD output_tokens INT DEFAULT 0'))
                else:
                    db.session.execute(text('ALTER TABLE messages ADD COLUMN output_tokens INTEGER DEFAULT 0'))
                print("[OK] output_tokens column added!")
            else:
                print("[=] output_tokens column already exists, skipping...")

            # Add is_estimated column to track if tokens were estimated (for local models)
            if 'tokens_estimated' not in existing_columns:
                print("Adding column: tokens_estimated")
                if dialect == 'mssql':
                    db.session.execute(text('ALTER TABLE messages ADD tokens_estimated BIT DEFAULT 0'))
                else:
                    db.session.execute(text('ALTER TABLE messages ADD COLUMN tokens_estimated BOOLEAN DEFAULT 0'))
                print("[OK] tokens_estimated column added!")
            else:
                print("[=] tokens_estimated column already exists, skipping...")

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error during migration: {str(e)}")
            raise


if __name__ == '__main__':
    print("=" * 60)
    print("Migration: Add token tracking columns to messages table")
    print("=" * 60)
    add_token_tracking()
    print("\nMigration complete!")
