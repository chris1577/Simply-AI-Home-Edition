"""
Migration script to add session_token column to users table.
This enables single-session enforcement (one device login at a time).

Usage: python scripts/migrations/add_session_token.py
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from sqlalchemy import text


def add_session_token():
    """Add session_token column to users table"""
    app = create_app('development')

    with app.app_context():
        try:
            # Check if column already exists
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('users')]

            if 'session_token' not in existing_columns:
                dialect = db.engine.dialect.name
                print("Adding column: session_token")

                if dialect == 'mssql':
                    # SQL Server syntax
                    db.session.execute(text('ALTER TABLE users ADD session_token VARCHAR(64) NULL'))
                    # Add index for faster lookups
                    db.session.execute(text('CREATE INDEX ix_users_session_token ON users(session_token)'))
                else:
                    # SQLite syntax
                    db.session.execute(text('ALTER TABLE users ADD COLUMN session_token VARCHAR(64)'))
                    # SQLite supports creating indexes after column add
                    db.session.execute(text('CREATE INDEX IF NOT EXISTS ix_users_session_token ON users(session_token)'))

                db.session.commit()
                print("[OK] session_token column added successfully!")
            else:
                print("[=] session_token column already exists, skipping...")

        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error during migration: {str(e)}")
            raise


if __name__ == '__main__':
    print("=" * 60)
    print("Migration: Add session_token column to users table")
    print("=" * 60)
    add_session_token()
    print("\nMigration complete!")
