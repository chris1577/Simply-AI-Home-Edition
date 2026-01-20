"""
Migration script to add date_of_birth column to users table.
Run this script to update existing databases.

Usage: python scripts/migrations/add_date_of_birth.py
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from sqlalchemy import text


def add_date_of_birth():
    """Add date_of_birth column to users table"""
    app = create_app('development')

    with app.app_context():
        try:
            # Check if column already exists
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('users')]

            if 'date_of_birth' not in existing_columns:
                dialect = db.engine.dialect.name
                print("Adding column: date_of_birth")

                if dialect == 'mssql':
                    # SQL Server syntax
                    db.session.execute(text('ALTER TABLE users ADD date_of_birth DATE NULL'))
                else:
                    # SQLite syntax
                    db.session.execute(text('ALTER TABLE users ADD COLUMN date_of_birth DATE'))

                db.session.commit()
                print("[OK] date_of_birth column added successfully!")
            else:
                print("[=] date_of_birth column already exists, skipping...")

        except Exception as e:
            db.session.rollback()
            print(f"[ERROR] Error during migration: {str(e)}")
            raise


if __name__ == '__main__':
    print("=" * 60)
    print("Migration: Add date_of_birth column to users table")
    print("=" * 60)
    add_date_of_birth()
    print("\nMigration complete!")
