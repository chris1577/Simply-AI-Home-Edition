"""
Migration script to add API provider model ID columns to user_settings table.
Run this script once to update existing databases.
"""

import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from sqlalchemy import text

def migrate_database():
    """Add new model ID columns to user_settings table"""
    app = create_app()

    with app.app_context():
        try:
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('user_settings')]

            columns_to_add = [
                ('gemini_model_id', 'VARCHAR(100)'),
                ('openai_model_id', 'VARCHAR(100)'),
                ('anthropic_model_id', 'VARCHAR(100)'),
                ('xai_model_id', 'VARCHAR(100)')
            ]

            # Detect database type for correct syntax
            dialect = db.engine.dialect.name

            added_columns = []
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    print(f"Adding column: {column_name}")
                    # SQL Server uses ADD, SQLite uses ADD COLUMN
                    if dialect == 'mssql':
                        db.session.execute(text(f'ALTER TABLE user_settings ADD {column_name} {column_type} NULL'))
                    else:
                        db.session.execute(text(f'ALTER TABLE user_settings ADD COLUMN {column_name} {column_type}'))
                    added_columns.append(column_name)
                else:
                    print(f"Column {column_name} already exists, skipping...")

            if added_columns:
                db.session.commit()
                print(f"\nSuccessfully added {len(added_columns)} column(s): {', '.join(added_columns)}")
            else:
                print("\nAll columns already exist. No migration needed.")

        except Exception as e:
            db.session.rollback()
            print(f"\nError during migration: {str(e)}")
            raise

if __name__ == '__main__':
    migrate_database()
