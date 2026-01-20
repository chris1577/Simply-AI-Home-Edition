"""
Database migration script to add attachments table.
Run this script to update the database with attachment support.
"""
import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.attachment import Attachment


def main():
    """Add attachments table to the database."""
    print("Adding attachments table to database...")

    app = create_app()

    with app.app_context():
        try:
            # Create the attachments table
            db.create_all()

            print("SUCCESS: Attachments table created successfully!")
            print("\nThe following table was added:")
            print("   - attachments (for file attachments in messages)")
            print("\nDatabase migration completed!")
            print("\nYou can now attach images and documents to your chat messages!")

        except Exception as e:
            print(f"ERROR: Error creating attachments table: {e}")
            return 1

    return 0


if __name__ == "__main__":
    exit(main())
