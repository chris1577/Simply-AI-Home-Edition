"""
Database migration script to add RAG (Retrieval-Augmented Generation) tables.
Run this script to add document storage and chunking support for RAG functionality.
"""
import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.document import Document, DocumentChunk
from app.models.admin_settings import AdminSettings


def add_rag_admin_settings(app):
    """Add RAG-related admin settings."""
    rag_settings = [
        ('rag_enabled', 'true', 'boolean', 'Enable RAG functionality globally'),
        ('rag_default_chunk_size', '512', 'integer', 'Default chunk size in tokens'),
        ('rag_default_overlap', '50', 'integer', 'Default chunk overlap in tokens'),
        ('rag_default_top_k', '5', 'integer', 'Default number of chunks to retrieve'),
        ('rag_embedding_model', 'openai', 'string', 'Embedding model provider: openai or local'),
        ('rag_max_documents_per_user', '50', 'integer', 'Maximum documents per user'),
        ('rag_min_similarity_score', '0.7', 'string', 'Minimum similarity score for retrieval (0.0-1.0)'),
    ]

    with app.app_context():
        for key, value, setting_type, description in rag_settings:
            existing = AdminSettings.query.filter_by(setting_key=key).first()
            if not existing:
                setting = AdminSettings(
                    setting_key=key,
                    setting_value=value,
                    setting_type=setting_type,
                    description=description
                )
                db.session.add(setting)
                print(f"   Added setting: {key} = {value}")
            else:
                print(f"   Setting already exists: {key}")

        db.session.commit()


def main():
    """Add RAG tables to the database."""
    print("=" * 60)
    print("RAG Tables Migration")
    print("=" * 60)
    print("\nAdding RAG (Retrieval-Augmented Generation) tables to database...")

    app = create_app()

    with app.app_context():
        try:
            # Check if tables already exist
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()

            tables_to_create = []
            if 'documents' not in existing_tables:
                tables_to_create.append('documents')
            if 'document_chunks' not in existing_tables:
                tables_to_create.append('document_chunks')

            if not tables_to_create:
                print("\nRAG tables already exist. Checking admin settings...")
            else:
                # Create the tables
                db.create_all()
                print(f"\nSUCCESS: Created tables: {', '.join(tables_to_create)}")

            print("\nThe following tables are now available:")
            print("   - documents (user-uploaded documents for RAG)")
            print("   - document_chunks (chunked document content with embeddings)")

        except Exception as e:
            print(f"\nERROR: Error creating RAG tables: {e}")
            import traceback
            traceback.print_exc()
            return 1

    # Add admin settings
    print("\nAdding RAG admin settings...")
    try:
        add_rag_admin_settings(app)
        print("\nSUCCESS: RAG admin settings configured!")
    except Exception as e:
        print(f"\nWARNING: Error adding admin settings: {e}")
        # Don't fail the migration for settings issues

    # Create ChromaDB data directory
    chroma_dir = os.path.join(project_root, 'data', 'chroma')
    if not os.path.exists(chroma_dir):
        os.makedirs(chroma_dir)
        print(f"\nCreated ChromaDB data directory: {chroma_dir}")
    else:
        print(f"\nChromaDB data directory already exists: {chroma_dir}")

    # Create RAG documents upload directory
    rag_docs_dir = os.path.join(project_root, 'uploads', 'rag_documents')
    if not os.path.exists(rag_docs_dir):
        os.makedirs(rag_docs_dir)
        print(f"Created RAG documents directory: {rag_docs_dir}")
    else:
        print(f"RAG documents directory already exists: {rag_docs_dir}")

    print("\n" + "=" * 60)
    print("RAG Migration Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Install RAG dependencies: pip install -r requirements.txt")
    print("2. Documents can now be uploaded for RAG processing")
    print("3. Configure RAG settings in Admin panel")

    return 0


if __name__ == "__main__":
    exit(main())
