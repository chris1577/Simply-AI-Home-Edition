"""
Vector store service for RAG.
Manages ChromaDB collections for document embeddings.
"""
import os
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorStore:
    """Service for managing ChromaDB vector storage."""

    # Collection naming
    COLLECTION_PREFIX = 'user_'

    # ChromaDB client singleton
    _client = None
    _initialized = False

    @staticmethod
    def get_client():
        """Get or create ChromaDB client with persistent storage."""
        if VectorStore._client is not None:
            return VectorStore._client

        try:
            import chromadb
            from chromadb.config import Settings

            # Determine storage path
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            chroma_path = os.path.join(base_dir, 'data', 'chroma')

            # Ensure directory exists
            Path(chroma_path).mkdir(parents=True, exist_ok=True)

            # Create persistent client
            VectorStore._client = chromadb.PersistentClient(
                path=chroma_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            VectorStore._initialized = True
            logger.info(f"ChromaDB initialized at: {chroma_path}")

            return VectorStore._client

        except ImportError:
            logger.error("chromadb not installed. Run: pip install chromadb")
            return None
        except Exception as e:
            logger.error(f"Error initializing ChromaDB: {str(e)}")
            return None

    @staticmethod
    def get_user_collection(user_id: int, create: bool = True):
        """
        Get or create a collection for a user.

        Args:
            user_id: User ID
            create: If True, create collection if it doesn't exist

        Returns:
            ChromaDB collection or None
        """
        client = VectorStore.get_client()
        if client is None:
            return None

        collection_name = f"{VectorStore.COLLECTION_PREFIX}{user_id}"

        try:
            if create:
                # Get or create collection
                collection = client.get_or_create_collection(
                    name=collection_name,
                    metadata={"user_id": user_id}
                )
            else:
                # Only get if exists
                try:
                    collection = client.get_collection(name=collection_name)
                except Exception:
                    return None

            return collection

        except Exception as e:
            logger.error(f"Error getting collection for user {user_id}: {str(e)}")
            return None

    @staticmethod
    def add_chunks(
        user_id: int,
        chunks: list,
        embeddings: list,
        document_id: int
    ) -> dict:
        """
        Add document chunks to user's collection.

        Args:
            user_id: User ID
            chunks: List of chunk dictionaries (content, chunk_index, etc.)
            embeddings: List of embedding vectors
            document_id: Document ID for reference

        Returns:
            dict with keys:
                - success: bool
                - chroma_ids: List of ChromaDB IDs for the chunks
                - error: Error message if failed
        """
        if len(chunks) != len(embeddings):
            return {
                'success': False,
                'chroma_ids': [],
                'error': 'Chunks and embeddings count mismatch'
            }

        collection = VectorStore.get_user_collection(user_id)
        if collection is None:
            return {
                'success': False,
                'chroma_ids': [],
                'error': 'Could not get user collection'
            }

        try:
            # Generate unique IDs for each chunk
            import uuid
            chroma_ids = [str(uuid.uuid4()) for _ in chunks]

            # Prepare data for ChromaDB
            documents = [chunk['content'] for chunk in chunks]
            metadatas = []

            for i, chunk in enumerate(chunks):
                metadatas.append({
                    'document_id': document_id,
                    'chunk_index': chunk.get('chunk_index', i),
                    'page_number': chunk.get('page_number') or 0,
                    'token_count': chunk.get('token_count', 0),
                    'start_char': chunk.get('start_char', 0),
                    'end_char': chunk.get('end_char', 0),
                })

            # Add to collection
            collection.add(
                ids=chroma_ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )

            logger.info(f"Added {len(chunks)} chunks to collection for user {user_id}, document {document_id}")

            return {
                'success': True,
                'chroma_ids': chroma_ids,
                'error': None
            }

        except Exception as e:
            logger.error(f"Error adding chunks to collection: {str(e)}")
            return {
                'success': False,
                'chroma_ids': [],
                'error': f'Failed to add chunks: {str(e)}'
            }

    @staticmethod
    def query(
        user_id: int,
        query_embedding: list,
        n_results: int = 5,
        document_ids: list = None
    ) -> dict:
        """
        Query user's collection for similar chunks.

        Args:
            user_id: User ID
            query_embedding: Query embedding vector
            n_results: Number of results to return
            document_ids: Optional list of document IDs to filter by

        Returns:
            dict with keys:
                - results: List of result dictionaries
                - error: Error message if failed
        """
        collection = VectorStore.get_user_collection(user_id, create=False)
        if collection is None:
            return {
                'results': [],
                'error': 'User has no document collection'
            }

        try:
            # Build where filter if document_ids specified
            where_filter = None
            if document_ids:
                if len(document_ids) == 1:
                    where_filter = {"document_id": document_ids[0]}
                else:
                    where_filter = {"document_id": {"$in": document_ids}}

            # Query collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=['documents', 'metadatas', 'distances']
            )

            # Format results
            formatted_results = []
            if results and results['ids'] and results['ids'][0]:
                for i, chroma_id in enumerate(results['ids'][0]):
                    distance = results['distances'][0][i] if results['distances'] else 0
                    # Convert distance to similarity score (ChromaDB uses L2 distance by default)
                    # Lower distance = higher similarity
                    similarity = 1 / (1 + distance)

                    formatted_results.append({
                        'chroma_id': chroma_id,
                        'content': results['documents'][0][i] if results['documents'] else '',
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': distance,
                        'similarity': similarity,
                    })

            return {
                'results': formatted_results,
                'error': None
            }

        except Exception as e:
            logger.error(f"Error querying collection: {str(e)}")
            return {
                'results': [],
                'error': f'Query failed: {str(e)}'
            }

    @staticmethod
    def delete_document(user_id: int, document_id: int) -> dict:
        """
        Delete all chunks for a document from vector store.

        Args:
            user_id: User ID
            document_id: Document ID

        Returns:
            dict with keys:
                - success: bool
                - deleted_count: Number of chunks deleted
                - error: Error message if failed
        """
        collection = VectorStore.get_user_collection(user_id, create=False)
        if collection is None:
            return {
                'success': True,
                'deleted_count': 0,
                'error': None
            }

        try:
            # Get chunks for this document
            results = collection.get(
                where={"document_id": document_id},
                include=['metadatas']
            )

            if results and results['ids']:
                # Delete the chunks
                collection.delete(ids=results['ids'])
                deleted_count = len(results['ids'])
                logger.info(f"Deleted {deleted_count} chunks for document {document_id}")

                return {
                    'success': True,
                    'deleted_count': deleted_count,
                    'error': None
                }

            return {
                'success': True,
                'deleted_count': 0,
                'error': None
            }

        except Exception as e:
            logger.error(f"Error deleting document from collection: {str(e)}")
            return {
                'success': False,
                'deleted_count': 0,
                'error': f'Delete failed: {str(e)}'
            }

    @staticmethod
    def delete_chunks_by_ids(user_id: int, chroma_ids: list) -> dict:
        """
        Delete specific chunks by their ChromaDB IDs.

        Args:
            user_id: User ID
            chroma_ids: List of ChromaDB chunk IDs

        Returns:
            dict with keys:
                - success: bool
                - error: Error message if failed
        """
        collection = VectorStore.get_user_collection(user_id, create=False)
        if collection is None:
            return {'success': True, 'error': None}

        try:
            collection.delete(ids=chroma_ids)
            return {'success': True, 'error': None}
        except Exception as e:
            logger.error(f"Error deleting chunks: {str(e)}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_collection_stats(user_id: int) -> dict:
        """
        Get statistics for a user's collection.

        Args:
            user_id: User ID

        Returns:
            dict with collection statistics
        """
        collection = VectorStore.get_user_collection(user_id, create=False)
        if collection is None:
            return {
                'exists': False,
                'count': 0,
                'error': None
            }

        try:
            count = collection.count()
            return {
                'exists': True,
                'count': count,
                'name': collection.name,
                'error': None
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {str(e)}")
            return {
                'exists': False,
                'count': 0,
                'error': str(e)
            }

    @staticmethod
    def delete_user_collection(user_id: int) -> dict:
        """
        Delete entire collection for a user.

        Args:
            user_id: User ID

        Returns:
            dict with keys:
                - success: bool
                - error: Error message if failed
        """
        client = VectorStore.get_client()
        if client is None:
            return {'success': False, 'error': 'ChromaDB not available'}

        collection_name = f"{VectorStore.COLLECTION_PREFIX}{user_id}"

        try:
            client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection for user {user_id}")
            return {'success': True, 'error': None}
        except Exception as e:
            # Collection might not exist, which is fine
            if 'does not exist' in str(e).lower():
                return {'success': True, 'error': None}
            logger.error(f"Error deleting collection: {str(e)}")
            return {'success': False, 'error': str(e)}
