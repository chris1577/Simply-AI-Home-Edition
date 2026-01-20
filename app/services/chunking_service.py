"""
Document chunking service.
Splits documents into chunks for embedding and retrieval.
"""
import re
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for splitting documents into chunks for embedding."""

    # Default settings
    DEFAULT_CHUNK_SIZE = 512  # tokens
    DEFAULT_CHUNK_OVERLAP = 50  # tokens
    DEFAULT_MIN_CHUNK_SIZE = 50  # minimum tokens per chunk

    # Approximate characters per token (for estimation)
    CHARS_PER_TOKEN = 4

    @staticmethod
    def chunk_document(
        text: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
        pages: list = None
    ) -> list:
        """
        Split document text into chunks for embedding.

        Args:
            text: Full document text
            chunk_size: Maximum tokens per chunk
            overlap: Number of overlapping tokens between chunks
            pages: Optional list of page texts (for respecting page boundaries in PDFs)

        Returns:
            List of chunk dictionaries with keys:
                - content: Chunk text
                - token_count: Estimated token count
                - start_char: Start position in original text
                - end_char: End position in original text
                - page_number: Page number if from a paged document
        """
        if not text or not text.strip():
            return []

        # Use tiktoken for accurate token counting if available
        tokenizer = ChunkingService._get_tokenizer()

        # If we have page-based content, chunk by page first
        if pages and len(pages) > 0:
            return ChunkingService._chunk_with_pages(
                pages, chunk_size, overlap, tokenizer
            )

        # Otherwise, chunk the full text
        return ChunkingService._chunk_text(
            text, chunk_size, overlap, tokenizer
        )

    @staticmethod
    def _get_tokenizer():
        """Get tiktoken tokenizer if available."""
        try:
            import tiktoken
            # Use cl100k_base (GPT-4/ChatGPT tokenizer) as default
            return tiktoken.get_encoding("cl100k_base")
        except ImportError:
            logger.warning("tiktoken not available, using character-based estimation")
            return None
        except Exception as e:
            logger.warning(f"Error loading tiktoken: {e}")
            return None

    @staticmethod
    def _count_tokens(text: str, tokenizer) -> int:
        """Count tokens in text."""
        if tokenizer:
            try:
                return len(tokenizer.encode(text))
            except Exception:
                pass
        # Fallback to character-based estimation
        return len(text) // ChunkingService.CHARS_PER_TOKEN

    @staticmethod
    def _chunk_with_pages(
        pages: list,
        chunk_size: int,
        overlap: int,
        tokenizer
    ) -> list:
        """Chunk document respecting page boundaries."""
        chunks = []
        overall_char_offset = 0

        for page_num, page_text in enumerate(pages, start=1):
            if not page_text or not page_text.strip():
                overall_char_offset += len(page_text) + 2  # Account for page separator
                continue

            # Chunk this page
            page_chunks = ChunkingService._chunk_text(
                page_text, chunk_size, overlap, tokenizer,
                start_offset=overall_char_offset
            )

            # Add page number to each chunk
            for chunk in page_chunks:
                chunk['page_number'] = page_num
                chunks.append(chunk)

            overall_char_offset += len(page_text) + 2  # Account for \n\n separator

        return chunks

    @staticmethod
    def _chunk_text(
        text: str,
        chunk_size: int,
        overlap: int,
        tokenizer,
        start_offset: int = 0
    ) -> list:
        """
        Chunk text using semantic splitting with fallback to sentence/word splitting.
        """
        chunks = []

        # Clean text
        text = text.strip()
        if not text:
            return chunks

        # Split into sentences for better semantic chunks
        sentences = ChunkingService._split_into_sentences(text)

        current_chunk = []
        current_tokens = 0
        current_start = start_offset

        for sentence in sentences:
            sentence_tokens = ChunkingService._count_tokens(sentence, tokenizer)

            # If single sentence is larger than chunk_size, split it further
            if sentence_tokens > chunk_size:
                # First, save current chunk if any
                if current_chunk:
                    chunk_text = ' '.join(current_chunk)
                    chunks.append({
                        'content': chunk_text,
                        'token_count': current_tokens,
                        'start_char': current_start,
                        'end_char': current_start + len(chunk_text),
                        'page_number': None
                    })

                # Split the large sentence into smaller pieces
                sub_chunks = ChunkingService._split_large_text(
                    sentence, chunk_size, overlap, tokenizer, start_offset
                )
                chunks.extend(sub_chunks)

                # Reset for next chunk
                current_chunk = []
                current_tokens = 0
                current_start = start_offset + len(text[:text.find(sentence) + len(sentence)])
                continue

            # Check if adding this sentence would exceed chunk size
            if current_tokens + sentence_tokens > chunk_size and current_chunk:
                # Save current chunk
                chunk_text = ' '.join(current_chunk)
                chunks.append({
                    'content': chunk_text,
                    'token_count': current_tokens,
                    'start_char': current_start,
                    'end_char': current_start + len(chunk_text),
                    'page_number': None
                })

                # Handle overlap - keep last few sentences
                overlap_sentences = []
                overlap_tokens = 0
                for s in reversed(current_chunk):
                    s_tokens = ChunkingService._count_tokens(s, tokenizer)
                    if overlap_tokens + s_tokens <= overlap:
                        overlap_sentences.insert(0, s)
                        overlap_tokens += s_tokens
                    else:
                        break

                current_chunk = overlap_sentences
                current_tokens = overlap_tokens
                current_start = start_offset + len(chunk_text) - len(' '.join(overlap_sentences))

            current_chunk.append(sentence)
            current_tokens += sentence_tokens

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if ChunkingService._count_tokens(chunk_text, tokenizer) >= ChunkingService.DEFAULT_MIN_CHUNK_SIZE:
                chunks.append({
                    'content': chunk_text,
                    'token_count': current_tokens,
                    'start_char': current_start,
                    'end_char': current_start + len(chunk_text),
                    'page_number': None
                })

        return chunks

    @staticmethod
    def _split_into_sentences(text: str) -> list:
        """Split text into sentences."""
        # Pattern to split on sentence boundaries
        # Handles: . ! ? followed by space and capital letter or end of string
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])$'

        # Split but preserve the delimiters
        parts = re.split(sentence_pattern, text)

        # Filter empty strings and strip whitespace
        sentences = [s.strip() for s in parts if s and s.strip()]

        # If no sentences found (no proper punctuation), split by newlines or return as is
        if len(sentences) <= 1 and len(text) > 500:
            # Try splitting by double newlines (paragraphs)
            paragraphs = text.split('\n\n')
            if len(paragraphs) > 1:
                sentences = [p.strip() for p in paragraphs if p.strip()]
            else:
                # Try splitting by single newlines
                lines = text.split('\n')
                if len(lines) > 1:
                    sentences = [l.strip() for l in lines if l.strip()]

        return sentences

    @staticmethod
    def _split_large_text(
        text: str,
        chunk_size: int,
        overlap: int,
        tokenizer,
        start_offset: int
    ) -> list:
        """Split a large piece of text that's bigger than chunk_size."""
        chunks = []
        words = text.split()

        current_words = []
        current_tokens = 0
        current_start = start_offset

        for word in words:
            word_tokens = ChunkingService._count_tokens(word + ' ', tokenizer)

            if current_tokens + word_tokens > chunk_size and current_words:
                # Save current chunk
                chunk_text = ' '.join(current_words)
                chunks.append({
                    'content': chunk_text,
                    'token_count': current_tokens,
                    'start_char': current_start,
                    'end_char': current_start + len(chunk_text),
                    'page_number': None
                })

                # Handle overlap
                overlap_words = []
                overlap_tokens = 0
                for w in reversed(current_words):
                    w_tokens = ChunkingService._count_tokens(w + ' ', tokenizer)
                    if overlap_tokens + w_tokens <= overlap:
                        overlap_words.insert(0, w)
                        overlap_tokens += w_tokens
                    else:
                        break

                current_words = overlap_words
                current_tokens = overlap_tokens
                current_start += len(chunk_text) - len(' '.join(overlap_words))

            current_words.append(word)
            current_tokens += word_tokens

        # Last chunk
        if current_words:
            chunk_text = ' '.join(current_words)
            chunks.append({
                'content': chunk_text,
                'token_count': current_tokens,
                'start_char': current_start,
                'end_char': current_start + len(chunk_text),
                'page_number': None
            })

        return chunks

    @staticmethod
    def estimate_chunks(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> int:
        """Estimate the number of chunks that will be created."""
        if not text:
            return 0

        tokenizer = ChunkingService._get_tokenizer()
        total_tokens = ChunkingService._count_tokens(text, tokenizer)

        # Rough estimate accounting for overlap
        estimated_chunks = max(1, total_tokens // (chunk_size - ChunkingService.DEFAULT_CHUNK_OVERLAP))
        return estimated_chunks

    @staticmethod
    def get_total_tokens(text: str) -> int:
        """Get total token count for text."""
        if not text:
            return 0

        tokenizer = ChunkingService._get_tokenizer()
        return ChunkingService._count_tokens(text, tokenizer)
