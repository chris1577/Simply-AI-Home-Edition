"""
RAG (Retrieval-Augmented Generation) service.
Orchestrates document processing, embedding, and retrieval.
"""
import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app import db
from app.models.document import Document, DocumentChunk
from app.models.admin_settings import AdminSettings
from app.services.document_extractor import DocumentExtractor
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGService:
    """Main RAG orchestration service."""

    # Default settings
    DEFAULT_TOP_K = 5
    DEFAULT_MIN_SCORE = 0.7
    DEFAULT_CHUNK_SIZE = 512
    DEFAULT_CHUNK_OVERLAP = 50

    @staticmethod
    def is_enabled() -> bool:
        """Check if RAG is enabled globally."""
        try:
            setting = AdminSettings.query.filter_by(setting_key='rag_enabled').first()
            if setting:
                return setting.setting_value.lower() == 'true'
            return True  # Default to enabled
        except Exception:
            return True

    @staticmethod
    def get_settings() -> dict:
        """Get all RAG settings."""
        defaults = {
            'rag_enabled': True,
            'rag_default_chunk_size': RAGService.DEFAULT_CHUNK_SIZE,
            'rag_default_overlap': RAGService.DEFAULT_CHUNK_OVERLAP,
            'rag_default_top_k': RAGService.DEFAULT_TOP_K,
            'rag_embedding_model': 'gemini',
            'rag_max_documents_per_user': 50,
            'rag_min_similarity_score': RAGService.DEFAULT_MIN_SCORE,
        }

        try:
            settings = {}
            for key, default in defaults.items():
                setting = AdminSettings.query.filter_by(setting_key=key).first()
                if setting:
                    # Convert based on type
                    if setting.setting_type == 'boolean':
                        settings[key] = setting.setting_value.lower() == 'true'
                    elif setting.setting_type == 'integer':
                        settings[key] = int(setting.setting_value)
                    elif setting.setting_type == 'string':
                        try:
                            settings[key] = float(setting.setting_value)
                        except ValueError:
                            settings[key] = setting.setting_value
                    else:
                        settings[key] = setting.setting_value
                else:
                    settings[key] = default
            return settings
        except Exception as e:
            logger.error(f"Error getting RAG settings: {str(e)}")
            return defaults

    @staticmethod
    def get_embedding_provider() -> str:
        """Get the configured embedding provider."""
        settings = RAGService.get_settings()
        return settings.get('rag_embedding_model', 'gemini')

    @staticmethod
    def process_document(document_id: int) -> dict:
        """
        Process a document: extract text, chunk, embed, and store.

        Args:
            document_id: Document ID to process

        Returns:
            dict with keys:
                - success: bool
                - chunk_count: Number of chunks created
                - total_tokens: Total tokens in document
                - error: Error message if failed
        """
        # Get document
        document = Document.query.get(document_id)
        if not document:
            return {
                'success': False,
                'chunk_count': 0,
                'total_tokens': 0,
                'error': 'Document not found'
            }

        # Mark as processing
        document.mark_processing()
        db.session.commit()

        try:
            # Get settings
            settings = RAGService.get_settings()
            chunk_size = settings.get('rag_default_chunk_size', RAGService.DEFAULT_CHUNK_SIZE)
            chunk_overlap = settings.get('rag_default_overlap', RAGService.DEFAULT_CHUNK_OVERLAP)
            embedding_provider = settings.get('rag_embedding_model', 'gemini')

            # Resolve file path
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            file_path = os.path.join(base_dir, 'uploads', document.file_path)

            # Step 1: Extract text
            logger.info(f"Extracting text from document {document_id}: {document.original_filename}")
            extraction_result = DocumentExtractor.extract(file_path, document.file_type)

            if extraction_result.get('error'):
                document.mark_failed(f"Extraction failed: {extraction_result['error']}")
                db.session.commit()
                return {
                    'success': False,
                    'chunk_count': 0,
                    'total_tokens': 0,
                    'error': extraction_result['error']
                }

            text = extraction_result.get('text', '')
            pages = extraction_result.get('pages', [])

            if not text or not text.strip():
                document.mark_failed("No text content extracted from document")
                db.session.commit()
                return {
                    'success': False,
                    'chunk_count': 0,
                    'total_tokens': 0,
                    'error': 'No text content in document'
                }

            # Step 2: Chunk document
            logger.info(f"Chunking document {document_id}")
            chunks = ChunkingService.chunk_document(
                text=text,
                chunk_size=chunk_size,
                overlap=chunk_overlap,
                pages=pages if pages else None
            )

            if not chunks:
                document.mark_failed("Failed to create chunks from document")
                db.session.commit()
                return {
                    'success': False,
                    'chunk_count': 0,
                    'total_tokens': 0,
                    'error': 'No chunks created'
                }

            # Add chunk indices
            for i, chunk in enumerate(chunks):
                chunk['chunk_index'] = i

            # Step 3: Generate embeddings
            logger.info(f"Generating embeddings for {len(chunks)} chunks")
            chunk_texts = [chunk['content'] for chunk in chunks]
            embedding_result = EmbeddingService.get_embeddings_batch(chunk_texts, provider=embedding_provider)

            if embedding_result.get('error'):
                document.mark_failed(f"Embedding failed: {embedding_result['error']}")
                db.session.commit()
                return {
                    'success': False,
                    'chunk_count': 0,
                    'total_tokens': 0,
                    'error': embedding_result['error']
                }

            embeddings = embedding_result.get('embeddings', [])
            embedding_model = embedding_result.get('model', '')

            if len(embeddings) != len(chunks):
                document.mark_failed("Embedding count mismatch")
                db.session.commit()
                return {
                    'success': False,
                    'chunk_count': 0,
                    'total_tokens': 0,
                    'error': 'Embedding count mismatch'
                }

            # Step 4: Store in vector database
            logger.info(f"Storing {len(chunks)} chunks in vector store")
            store_result = VectorStore.add_chunks(
                user_id=document.user_id,
                chunks=chunks,
                embeddings=embeddings,
                document_id=document_id
            )

            if not store_result.get('success'):
                document.mark_failed(f"Vector store failed: {store_result.get('error')}")
                db.session.commit()
                return {
                    'success': False,
                    'chunk_count': 0,
                    'total_tokens': 0,
                    'error': store_result.get('error')
                }

            chroma_ids = store_result.get('chroma_ids', [])

            # Step 5: Save chunks to database
            logger.info(f"Saving {len(chunks)} chunks to database")
            total_tokens = 0

            for i, chunk in enumerate(chunks):
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_index=chunk['chunk_index'],
                    content=chunk['content'],
                    token_count=chunk.get('token_count', 0),
                    start_char=chunk.get('start_char'),
                    end_char=chunk.get('end_char'),
                    page_number=chunk.get('page_number'),
                    chroma_id=chroma_ids[i]
                )
                db.session.add(db_chunk)
                total_tokens += chunk.get('token_count', 0)

            # Step 6: Update document status
            document.mark_ready(
                chunk_count=len(chunks),
                total_tokens=total_tokens,
                embedding_model=embedding_model
            )
            db.session.commit()

            logger.info(f"Successfully processed document {document_id}: {len(chunks)} chunks, {total_tokens} tokens")

            return {
                'success': True,
                'chunk_count': len(chunks),
                'total_tokens': total_tokens,
                'error': None
            }

        except Exception as e:
            logger.error(f"Error processing document {document_id}: {str(e)}")
            document.mark_failed(str(e))
            db.session.commit()
            return {
                'success': False,
                'chunk_count': 0,
                'total_tokens': 0,
                'error': str(e)
            }

    @staticmethod
    def retrieve_context(
        user_id: int,
        query: str,
        top_k: int = None,
        min_score: float = None,
        document_ids: list = None,
        model_provider: str = None
    ) -> list:
        """
        Retrieve relevant document chunks for a query.

        Args:
            user_id: User ID
            query: Query text
            top_k: Number of chunks to retrieve
            min_score: Minimum similarity score
            document_ids: Optional list of document IDs to filter by
            model_provider: Optional chat model provider to determine embedding provider

        Returns:
            List of chunk dictionaries with content and metadata
        """
        if not RAGService.is_enabled():
            return []

        # Get settings
        settings = RAGService.get_settings()
        if top_k is None:
            top_k = settings.get('rag_default_top_k', RAGService.DEFAULT_TOP_K)
        if min_score is None:
            min_score = settings.get('rag_min_similarity_score', RAGService.DEFAULT_MIN_SCORE)

        # Determine embedding provider based on chat model provider
        if model_provider:
            embedding_provider = EmbeddingService.get_provider_for_model(model_provider)
        else:
            embedding_provider = settings.get('rag_embedding_model', 'gemini')

        try:
            # Generate query embedding
            embedding_result = EmbeddingService.get_embedding(query, provider=embedding_provider)

            if embedding_result.get('error'):
                logger.error(f"Query embedding failed: {embedding_result['error']}")
                return []

            query_embedding = embedding_result.get('embedding')
            if not query_embedding:
                return []

            # Query vector store
            query_result = VectorStore.query(
                user_id=user_id,
                query_embedding=query_embedding,
                n_results=top_k,
                document_ids=document_ids
            )

            if query_result.get('error'):
                logger.error(f"Vector query failed: {query_result['error']}")
                return []

            results = query_result.get('results', [])

            # Filter by minimum score
            filtered_results = [r for r in results if r.get('similarity', 0) >= min_score]

            # Enrich with document information
            enriched_results = []
            for result in filtered_results:
                metadata = result.get('metadata', {})
                doc_id = metadata.get('document_id')

                # Get document name
                doc_name = None
                if doc_id:
                    document = Document.query.get(doc_id)
                    if document:
                        doc_name = document.original_filename

                enriched_results.append({
                    'content': result.get('content', ''),
                    'document_id': doc_id,
                    'document_name': doc_name,
                    'chunk_index': metadata.get('chunk_index'),
                    'page_number': metadata.get('page_number'),
                    'similarity': result.get('similarity', 0),
                    'token_count': metadata.get('token_count', 0),
                })

            return enriched_results

        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}")
            return []

    @staticmethod
    def format_context_for_prompt(retrieved_chunks: list) -> str:
        """
        Format retrieved chunks as context for AI prompt.

        Args:
            retrieved_chunks: List of chunk dictionaries from retrieve_context()

        Returns:
            Formatted context string
        """
        if not retrieved_chunks:
            return ""

        context_parts = []
        context_parts.append("=== DOCUMENT CONTEXT ===\n")

        for i, chunk in enumerate(retrieved_chunks, 1):
            doc_name = chunk.get('document_name', 'Unknown Document')
            page_num = chunk.get('page_number')
            content = chunk.get('content', '')

            header = f"[Source {i}: {doc_name}"
            if page_num:
                header += f", Page {page_num}"
            header += "]"

            context_parts.append(header)
            context_parts.append(content)
            context_parts.append("")  # Empty line between chunks

        context_parts.append("=== END DOCUMENT CONTEXT ===")

        return "\n".join(context_parts)

    @staticmethod
    def delete_document(document_id: int) -> dict:
        """
        Delete a document and all associated data.

        Args:
            document_id: Document ID to delete

        Returns:
            dict with keys:
                - success: bool
                - error: Error message if failed
        """
        document = Document.query.get(document_id)
        if not document:
            return {'success': False, 'error': 'Document not found'}

        try:
            user_id = document.user_id

            # Delete from vector store
            VectorStore.delete_document(user_id, document_id)

            # Delete physical file
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            file_path = os.path.join(base_dir, 'uploads', document.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

            # Delete from database (cascades to chunks)
            db.session.delete(document)
            db.session.commit()

            logger.info(f"Deleted document {document_id}")

            return {'success': True, 'error': None}

        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_user_documents(user_id: int, project_id: int = None) -> list:
        """
        Get all documents for a user.

        Args:
            user_id: User ID
            project_id: Optional project ID to filter by

        Returns:
            List of document dictionaries
        """
        try:
            query = Document.query.filter_by(user_id=user_id)

            if project_id is not None:
                query = query.filter_by(project_id=project_id)

            documents = query.order_by(Document.created_at.desc()).all()

            return [doc.to_dict() for doc in documents]

        except Exception as e:
            logger.error(f"Error getting user documents: {str(e)}")
            return []

    @staticmethod
    def get_user_document_count(user_id: int) -> int:
        """Get the number of documents for a user."""
        try:
            return Document.query.filter_by(user_id=user_id).count()
        except Exception:
            return 0

    @staticmethod
    def can_upload_document(user_id: int) -> tuple:
        """
        Check if user can upload more documents.

        Returns:
            Tuple of (can_upload: bool, reason: str or None)
        """
        if not RAGService.is_enabled():
            return False, "RAG is disabled"

        settings = RAGService.get_settings()
        max_docs = settings.get('rag_max_documents_per_user', 50)

        current_count = RAGService.get_user_document_count(user_id)

        if current_count >= max_docs:
            return False, f"Maximum document limit reached ({max_docs})"

        return True, None

    @staticmethod
    def save_uploaded_document(
        user_id: int,
        file,
        project_id: int = None
    ) -> dict:
        """
        Save an uploaded document for RAG processing.

        Args:
            user_id: User ID
            file: File object from request
            project_id: Optional project ID

        Returns:
            dict with keys:
                - success: bool
                - document_id: ID of created document
                - error: Error message if failed
        """
        from werkzeug.utils import secure_filename

        # Check if user can upload
        can_upload, reason = RAGService.can_upload_document(user_id)
        if not can_upload:
            return {'success': False, 'document_id': None, 'error': reason}

        try:
            # Validate file
            if not file or not file.filename:
                return {'success': False, 'document_id': None, 'error': 'No file provided'}

            original_filename = secure_filename(file.filename)
            file_ext = Path(original_filename).suffix.lower().strip('.')

            if not DocumentExtractor.is_supported(file_ext):
                supported = ', '.join(DocumentExtractor.get_supported_extensions())
                return {
                    'success': False,
                    'document_id': None,
                    'error': f'Unsupported file type. Supported: {supported}'
                }

            # Generate storage path
            stored_filename = f"{uuid.uuid4()}.{file_ext}"
            relative_path = f"rag_documents/{stored_filename}"

            # Ensure directory exists
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            storage_dir = os.path.join(base_dir, 'uploads', 'rag_documents')
            Path(storage_dir).mkdir(parents=True, exist_ok=True)

            file_path = os.path.join(storage_dir, stored_filename)

            # Save file
            file.save(file_path)
            file_size = os.path.getsize(file_path)

            # Get MIME type
            import mimetypes
            mime_type, _ = mimetypes.guess_type(original_filename)
            mime_type = mime_type or 'application/octet-stream'

            # Create document record
            document = Document(
                user_id=user_id,
                project_id=project_id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=relative_path,
                mime_type=mime_type,
                file_size=file_size,
                file_type=file_ext,
                status='pending'
            )
            db.session.add(document)
            db.session.commit()

            logger.info(f"Saved document {document.id}: {original_filename}")

            return {
                'success': True,
                'document_id': document.id,
                'error': None
            }

        except Exception as e:
            logger.error(f"Error saving document: {str(e)}")
            db.session.rollback()
            return {'success': False, 'document_id': None, 'error': str(e)}

    @staticmethod
    def upload_and_process(
        user_id: int,
        file,
        project_id: int = None
    ) -> dict:
        """
        Upload and immediately process a document.

        Args:
            user_id: User ID
            file: File object from request
            project_id: Optional project ID

        Returns:
            dict with document info and processing results
        """
        # Save document
        save_result = RAGService.save_uploaded_document(user_id, file, project_id)

        if not save_result.get('success'):
            return save_result

        document_id = save_result.get('document_id')

        # Process document
        process_result = RAGService.process_document(document_id)

        return {
            'success': process_result.get('success'),
            'document_id': document_id,
            'chunk_count': process_result.get('chunk_count', 0),
            'total_tokens': process_result.get('total_tokens', 0),
            'error': process_result.get('error')
        }
