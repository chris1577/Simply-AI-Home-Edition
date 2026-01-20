"""
Migration script to add model_visibility table.
Run this script once to add the model visibility feature to existing databases.
"""

import sys
import os

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.model_visibility import ModelVisibility


def add_model_visibility_table():
    """Add model_visibility table and initialize with default models"""

    app = create_app('development')

    with app.app_context():
        try:
            # Create table
            print("Creating model_visibility table...")
            db.create_all()
            print("[OK] Table created successfully")

            # Initialize default models
            print("\nInitializing default model visibility settings...")
            ModelVisibility.initialize_default_models()
            print("[OK] Default models initialized")

            # Display current models
            print("\nCurrent models:")
            models = ModelVisibility.query.order_by(ModelVisibility.sort_order).all()
            for model in models:
                status = "[ENABLED]" if model.is_enabled else "[DISABLED]"
                print(f"  {model.sort_order}. {model.display_name} ({model.provider}) - {status}")

            print("\n[SUCCESS] Migration completed successfully!")
            print("\nNote: Only super_admin users can access the Admin Settings to manage model visibility.")

        except Exception as e:
            print(f"\n[ERROR] Error during migration: {str(e)}")
            db.session.rollback()
            raise


if __name__ == '__main__':
    print("=" * 60)
    print("Model Visibility Migration Script")
    print("=" * 60)
    print("\nThis script will:")
    print("1. Create the model_visibility table")
    print("2. Initialize default model visibility settings")
    print("\nAll models will be enabled by default.")
    print("=" * 60)

    response = input("\nDo you want to proceed? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        add_model_visibility_table()
    else:
        print("\nMigration cancelled.")
