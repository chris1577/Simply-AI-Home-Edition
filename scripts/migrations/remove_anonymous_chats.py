"""
Migration script to remove anonymous chat functionality.

This script:
1. Deletes all anonymous chat sessions (where user_id is NULL)
2. Deletes all associated messages and attachments
3. Removes physical attachment files from storage
4. Updates the database schema to make user_id non-nullable (already done in model)

Run this script once before deploying the updated code that requires authentication.

Usage:
    python scripts/migrations/remove_anonymous_chats.py
"""

import os
import sys

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models.chat import Chat, Message
from app.models.attachment import Attachment
from app.services.file_service import FileService
from sqlalchemy import text


def remove_anonymous_chats():
    """Remove all anonymous chats and their associated data"""
    app = create_app('development')

    with app.app_context():
        try:
            print("=" * 60)
            print("MIGRATION: Remove Anonymous Chat Support")
            print("=" * 60)
            print()

            # Get all anonymous chats (where user_id is NULL)
            anonymous_chats = Chat.query.filter_by(user_id=None).all()

            if not anonymous_chats:
                print("[OK] No anonymous chats found. Database is already clean.")
                print()
                return

            print(f"Found {len(anonymous_chats)} anonymous chat sessions to remove.")
            print()

            # Initialize file service for deleting attachment files
            upload_folder = app.config.get('UPLOAD_FOLDER', 'uploads')
            file_service = FileService(upload_folder)

            deleted_chats = 0
            deleted_messages = 0
            deleted_attachments = 0
            deleted_files = 0
            failed_files = 0

            # Process each anonymous chat
            for chat in anonymous_chats:
                print(f"Processing chat: {chat.name} (session_id: {chat.session_id})")

                # Get all messages in the chat
                messages = chat.messages.all()
                deleted_messages += len(messages)

                # Delete attachment files
                for message in messages:
                    for attachment in message.attachments:
                        # Try to delete the physical file
                        if file_service.delete_file(attachment.file_path):
                            deleted_files += 1
                        else:
                            failed_files += 1
                        deleted_attachments += 1

                # Delete the chat (cascade will handle messages and attachments in DB)
                db.session.delete(chat)
                deleted_chats += 1

            # Commit all deletions
            db.session.commit()

            print()
            print("=" * 60)
            print("MIGRATION COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print(f"[OK] Deleted {deleted_chats} anonymous chat sessions")
            print(f"[OK] Deleted {deleted_messages} messages")
            print(f"[OK] Deleted {deleted_attachments} attachment records")
            print(f"[OK] Deleted {deleted_files} attachment files")
            if failed_files > 0:
                print(f"[WARNING] Failed to delete {failed_files} files (may not exist)")
            print()
            print("Next steps:")
            print("1. The database schema has been updated (user_id is now required)")
            print("2. All routes now require authentication")
            print("3. Users must log in to access the chat interface")
            print()

        except Exception as e:
            db.session.rollback()
            print()
            print("=" * 60)
            print("ERROR: Migration failed!")
            print("=" * 60)
            print(f"Error: {str(e)}")
            print()
            print("The database has been rolled back. No changes were made.")
            print()
            raise


if __name__ == '__main__':
    print()
    response = input("This will DELETE all anonymous chat data. Continue? (yes/no): ")
    print()

    if response.lower() == 'yes':
        remove_anonymous_chats()
    else:
        print("Migration cancelled.")
        print()
