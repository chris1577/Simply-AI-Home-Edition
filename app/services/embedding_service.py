"""
Embedding service for RAG.
Generates vector embeddings using Gemini, OpenAI, or local models.
"""
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings."""

    # Model configurations
    GEMINI_MODEL = 'gemini-embedding-001'
    GEMINI_DIMENSIONS = 3072
    OPENAI_MODEL = 'text-embedding-3-small'
    OPENAI_DIMENSIONS = 1536
    LOCAL_MODEL = 'all-MiniLM-L12-v2'
    LOCAL_DIMENSIONS = 384

    # Cache for local model
    _local_model = None
    _local_model_loaded = False

    # Cache for Gemini client
    _gemini_client = None

    @staticmethod
    def get_embedding(
        text: str,
        provider: str = 'gemini'
    ) -> dict:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            provider: 'gemini', 'openai', or 'local'

        Returns:
            dict with keys:
                - embedding: List of floats (the vector)
                - dimensions: Number of dimensions
                - model: Model used
                - error: Error message if failed
        """
        if not text or not text.strip():
            return {
                'embedding': None,
                'dimensions': 0,
                'model': None,
                'error': 'Empty text provided'
            }

        provider = provider.lower()

        if provider == 'gemini':
            return EmbeddingService._get_gemini_embedding(text)
        elif provider == 'openai':
            return EmbeddingService._get_openai_embedding(text)
        elif provider == 'local':
            return EmbeddingService._get_local_embedding(text)
        else:
            # Default to Gemini, fall back to OpenAI, then local
            result = EmbeddingService._get_gemini_embedding(text)
            if result.get('error'):
                logger.warning(f"Gemini embedding failed, trying OpenAI: {result['error']}")
                result = EmbeddingService._get_openai_embedding(text)
                if result.get('error'):
                    logger.warning(f"OpenAI embedding failed, falling back to local: {result['error']}")
                    return EmbeddingService._get_local_embedding(text)
            return result

    @staticmethod
    def get_embeddings_batch(
        texts: list,
        provider: str = 'gemini'
    ) -> dict:
        """
        Generate embeddings for multiple texts (more efficient).

        Args:
            texts: List of texts to embed
            provider: 'gemini', 'openai', or 'local'

        Returns:
            dict with keys:
                - embeddings: List of embedding vectors
                - dimensions: Number of dimensions
                - model: Model used
                - error: Error message if failed
        """
        if not texts:
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': 'No texts provided'
            }

        # Filter empty texts
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': 'All texts were empty'
            }

        provider = provider.lower()

        if provider == 'gemini':
            return EmbeddingService._get_gemini_embeddings_batch(valid_texts)
        elif provider == 'openai':
            return EmbeddingService._get_openai_embeddings_batch(valid_texts)
        elif provider == 'local':
            return EmbeddingService._get_local_embeddings_batch(valid_texts)
        else:
            # Default to Gemini, fall back to OpenAI, then local
            result = EmbeddingService._get_gemini_embeddings_batch(valid_texts)
            if result.get('error'):
                logger.warning(f"Gemini batch embedding failed, trying OpenAI: {result['error']}")
                result = EmbeddingService._get_openai_embeddings_batch(valid_texts)
                if result.get('error'):
                    logger.warning(f"OpenAI batch embedding failed, falling back to local: {result['error']}")
                    return EmbeddingService._get_local_embeddings_batch(valid_texts)
            return result

    @staticmethod
    def _get_gemini_client():
        """Get or create Gemini client."""
        if EmbeddingService._gemini_client is None:
            api_key = os.getenv('GEMINI_API_KEY', '')
            if not api_key:
                return None
            try:
                from google import genai
                EmbeddingService._gemini_client = genai.Client(api_key=api_key)
                logger.info("Initialized Gemini client for embeddings")
            except ImportError:
                logger.error("google-genai package not installed")
                return None
            except Exception as e:
                logger.error(f"Error initializing Gemini client: {str(e)}")
                return None
        return EmbeddingService._gemini_client

    @staticmethod
    def _get_gemini_embedding(text: str) -> dict:
        """Get embedding using Gemini API."""
        api_key = os.getenv('GEMINI_API_KEY', '')

        if not api_key:
            return {
                'embedding': None,
                'dimensions': 0,
                'model': None,
                'error': 'GEMINI_API_KEY not configured'
            }

        client = EmbeddingService._get_gemini_client()
        if client is None:
            return {
                'embedding': None,
                'dimensions': 0,
                'model': None,
                'error': 'Failed to initialize Gemini client'
            }

        try:
            result = client.models.embed_content(
                model=EmbeddingService.GEMINI_MODEL,
                contents=[text]
            )

            # Get the first (and only) embedding
            embedding = list(result.embeddings[0].values)

            return {
                'embedding': embedding,
                'dimensions': len(embedding),
                'model': EmbeddingService.GEMINI_MODEL,
                'error': None
            }

        except Exception as e:
            logger.error(f"Gemini embedding error: {str(e)}")
            return {
                'embedding': None,
                'dimensions': 0,
                'model': None,
                'error': f'Gemini embedding failed: {str(e)}'
            }

    @staticmethod
    def _get_gemini_embeddings_batch(texts: list) -> dict:
        """Get embeddings for multiple texts using Gemini API."""
        api_key = os.getenv('GEMINI_API_KEY', '')

        if not api_key:
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': 'GEMINI_API_KEY not configured'
            }

        client = EmbeddingService._get_gemini_client()
        if client is None:
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': 'Failed to initialize Gemini client'
            }

        try:
            result = client.models.embed_content(
                model=EmbeddingService.GEMINI_MODEL,
                contents=texts
            )

            # Extract embeddings in order
            embeddings = [list(emb.values) for emb in result.embeddings]

            return {
                'embeddings': embeddings,
                'dimensions': len(embeddings[0]) if embeddings else 0,
                'model': EmbeddingService.GEMINI_MODEL,
                'error': None
            }

        except Exception as e:
            logger.error(f"Gemini batch embedding error: {str(e)}")
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': f'Gemini batch embedding failed: {str(e)}'
            }

    @staticmethod
    def _get_openai_embedding(text: str) -> dict:
        """Get embedding using OpenAI API."""
        api_key = os.getenv('OPENAI_API_KEY', '')

        if not api_key:
            return {
                'embedding': None,
                'dimensions': 0,
                'model': None,
                'error': 'OPENAI_API_KEY not configured'
            }

        try:
            response = requests.post(
                'https://api.openai.com/v1/embeddings',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'input': text,
                    'model': EmbeddingService.OPENAI_MODEL
                },
                timeout=30
            )

            if response.status_code != 200:
                error_msg = response.json().get('error', {}).get('message', response.text)
                return {
                    'embedding': None,
                    'dimensions': 0,
                    'model': None,
                    'error': f'OpenAI API error: {error_msg}'
                }

            data = response.json()
            embedding = data['data'][0]['embedding']

            return {
                'embedding': embedding,
                'dimensions': len(embedding),
                'model': EmbeddingService.OPENAI_MODEL,
                'error': None
            }

        except requests.exceptions.Timeout:
            return {
                'embedding': None,
                'dimensions': 0,
                'model': None,
                'error': 'OpenAI API request timed out'
            }
        except Exception as e:
            logger.error(f"OpenAI embedding error: {str(e)}")
            return {
                'embedding': None,
                'dimensions': 0,
                'model': None,
                'error': f'OpenAI embedding failed: {str(e)}'
            }

    @staticmethod
    def _get_openai_embeddings_batch(texts: list) -> dict:
        """Get embeddings for multiple texts using OpenAI API."""
        api_key = os.getenv('OPENAI_API_KEY', '')

        if not api_key:
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': 'OPENAI_API_KEY not configured'
            }

        try:
            response = requests.post(
                'https://api.openai.com/v1/embeddings',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'input': texts,
                    'model': EmbeddingService.OPENAI_MODEL
                },
                timeout=60
            )

            if response.status_code != 200:
                error_msg = response.json().get('error', {}).get('message', response.text)
                return {
                    'embeddings': [],
                    'dimensions': 0,
                    'model': None,
                    'error': f'OpenAI API error: {error_msg}'
                }

            data = response.json()
            # Sort by index to ensure correct order
            sorted_data = sorted(data['data'], key=lambda x: x['index'])
            embeddings = [item['embedding'] for item in sorted_data]

            return {
                'embeddings': embeddings,
                'dimensions': len(embeddings[0]) if embeddings else 0,
                'model': EmbeddingService.OPENAI_MODEL,
                'error': None
            }

        except requests.exceptions.Timeout:
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': 'OpenAI API request timed out'
            }
        except Exception as e:
            logger.error(f"OpenAI batch embedding error: {str(e)}")
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': f'OpenAI batch embedding failed: {str(e)}'
            }

    @staticmethod
    def _load_local_model():
        """Load the local sentence-transformers model."""
        if EmbeddingService._local_model_loaded:
            return EmbeddingService._local_model

        try:
            from sentence_transformers import SentenceTransformer
            EmbeddingService._local_model = SentenceTransformer(EmbeddingService.LOCAL_MODEL)
            EmbeddingService._local_model_loaded = True
            logger.info(f"Loaded local embedding model: {EmbeddingService.LOCAL_MODEL}")
            return EmbeddingService._local_model
        except ImportError:
            logger.error("sentence-transformers not installed")
            return None
        except Exception as e:
            logger.error(f"Error loading local model: {str(e)}")
            return None

    @staticmethod
    def _get_local_embedding(text: str) -> dict:
        """Get embedding using local sentence-transformers model."""
        model = EmbeddingService._load_local_model()

        if model is None:
            return {
                'embedding': None,
                'dimensions': 0,
                'model': None,
                'error': 'Local embedding model not available. Install: pip install sentence-transformers'
            }

        try:
            embedding = model.encode(text, convert_to_numpy=True).tolist()

            return {
                'embedding': embedding,
                'dimensions': len(embedding),
                'model': EmbeddingService.LOCAL_MODEL,
                'error': None
            }
        except Exception as e:
            logger.error(f"Local embedding error: {str(e)}")
            return {
                'embedding': None,
                'dimensions': 0,
                'model': None,
                'error': f'Local embedding failed: {str(e)}'
            }

    @staticmethod
    def _get_local_embeddings_batch(texts: list) -> dict:
        """Get embeddings for multiple texts using local model."""
        model = EmbeddingService._load_local_model()

        if model is None:
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': 'Local embedding model not available. Install: pip install sentence-transformers'
            }

        try:
            embeddings = model.encode(texts, convert_to_numpy=True).tolist()

            return {
                'embeddings': embeddings,
                'dimensions': len(embeddings[0]) if embeddings else 0,
                'model': EmbeddingService.LOCAL_MODEL,
                'error': None
            }
        except Exception as e:
            logger.error(f"Local batch embedding error: {str(e)}")
            return {
                'embeddings': [],
                'dimensions': 0,
                'model': None,
                'error': f'Local batch embedding failed: {str(e)}'
            }

    @staticmethod
    def get_dimensions(provider: str = 'gemini') -> int:
        """Get the embedding dimensions for a provider."""
        provider = provider.lower()
        if provider == 'local':
            return EmbeddingService.LOCAL_DIMENSIONS
        elif provider == 'openai':
            return EmbeddingService.OPENAI_DIMENSIONS
        return EmbeddingService.GEMINI_DIMENSIONS

    @staticmethod
    def get_model_name(provider: str = 'gemini') -> str:
        """Get the model name for a provider."""
        provider = provider.lower()
        if provider == 'local':
            return EmbeddingService.LOCAL_MODEL
        elif provider == 'openai':
            return EmbeddingService.OPENAI_MODEL
        return EmbeddingService.GEMINI_MODEL

    @staticmethod
    def is_available(provider: str = 'gemini') -> bool:
        """Check if embedding provider is available."""
        provider = provider.lower()
        if provider == 'gemini':
            return bool(os.getenv('GEMINI_API_KEY', ''))
        elif provider == 'openai':
            return bool(os.getenv('OPENAI_API_KEY', ''))
        elif provider == 'local':
            try:
                from sentence_transformers import SentenceTransformer
                return True
            except ImportError:
                return False
        return False

    @staticmethod
    def get_provider_for_model(model_provider: str) -> str:
        """
        Get the appropriate embedding provider based on the chat model provider.

        Args:
            model_provider: The AI model provider (e.g., 'gemini', 'openai', etc.)

        Returns:
            The embedding provider to use ('gemini', 'openai', or 'local')
        """
        model_provider = model_provider.lower()

        # Map chat providers to embedding providers
        if model_provider == 'openai':
            if EmbeddingService.is_available('openai'):
                return 'openai'
        elif model_provider == 'gemini':
            if EmbeddingService.is_available('gemini'):
                return 'gemini'

        # Fallback: use whichever is available
        if EmbeddingService.is_available('gemini'):
            return 'gemini'
        elif EmbeddingService.is_available('openai'):
            return 'openai'
        elif EmbeddingService.is_available('local'):
            return 'local'

        # Default to gemini (will fail gracefully if not configured)
        return 'gemini'
