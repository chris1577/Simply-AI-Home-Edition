"""
Token counting service for tracking AI API token usage.
Wraps tiktoken for accurate token counting across providers.
"""
import logging

logger = logging.getLogger(__name__)


class TokenService:
    """Service for counting and tracking tokens in messages."""

    # Approximate characters per token (fallback estimation)
    CHARS_PER_TOKEN = 4

    _tokenizer = None

    @classmethod
    def _get_tokenizer(cls):
        """Get tiktoken tokenizer (cached)."""
        if cls._tokenizer is None:
            try:
                import tiktoken
                # Use cl100k_base (GPT-4/ChatGPT tokenizer) as default
                cls._tokenizer = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                logger.warning("tiktoken not available, using character-based estimation")
                cls._tokenizer = False  # Mark as unavailable
            except Exception as e:
                logger.warning(f"Error loading tiktoken: {e}")
                cls._tokenizer = False
        return cls._tokenizer if cls._tokenizer else None

    @classmethod
    def count_tokens(cls, text: str) -> int:
        """
        Count tokens in text using tiktoken.

        Args:
            text: The text to count tokens for

        Returns:
            Number of tokens in the text
        """
        if not text:
            return 0

        tokenizer = cls._get_tokenizer()
        if tokenizer:
            try:
                return len(tokenizer.encode(text))
            except Exception as e:
                logger.warning(f"Error counting tokens: {e}")

        # Fallback to character-based estimation
        return len(text) // cls.CHARS_PER_TOKEN

    @classmethod
    def extract_usage_from_response(cls, response_data: dict, provider: str) -> dict:
        """
        Extract token usage from provider API response.

        Args:
            response_data: The raw API response data
            provider: The AI provider name (openai, anthropic, gemini, xai, lm_studio, ollama)

        Returns:
            Dictionary with keys: input_tokens, output_tokens, total_tokens, estimated
        """
        result = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'estimated': False
        }

        if not response_data:
            return result

        try:
            if provider in ('openai', 'xai', 'grok'):
                # OpenAI and xAI use the same format
                usage = response_data.get('usage', {})
                result['input_tokens'] = usage.get('prompt_tokens', 0)
                result['output_tokens'] = usage.get('completion_tokens', 0)
                result['total_tokens'] = usage.get('total_tokens', 0)

            elif provider == 'anthropic':
                # Anthropic format
                usage = response_data.get('usage', {})
                result['input_tokens'] = usage.get('input_tokens', 0)
                result['output_tokens'] = usage.get('output_tokens', 0)
                result['total_tokens'] = result['input_tokens'] + result['output_tokens']

            elif provider == 'gemini':
                # Gemini SDK format (usage_metadata)
                usage = response_data.get('usage_metadata', {})
                if usage:
                    result['input_tokens'] = usage.get('prompt_token_count', 0)
                    result['output_tokens'] = usage.get('candidates_token_count', 0)
                    result['total_tokens'] = usage.get('total_token_count', 0)

            elif provider in ('lm_studio', 'ollama'):
                # Local models typically don't provide token counts
                # Check if any usage data was provided (some local servers may support it)
                usage = response_data.get('usage', {})
                if usage:
                    result['input_tokens'] = usage.get('prompt_tokens', 0)
                    result['output_tokens'] = usage.get('completion_tokens', 0)
                    result['total_tokens'] = usage.get('total_tokens', 0)

        except Exception as e:
            logger.warning(f"Error extracting token usage from {provider} response: {e}")

        return result

    @classmethod
    def estimate_tokens(cls, text: str) -> dict:
        """
        Estimate token count for text (used when API doesn't provide counts).

        Args:
            text: The text to estimate tokens for

        Returns:
            Dictionary with estimated token counts
        """
        token_count = cls.count_tokens(text)
        return {
            'input_tokens': 0,
            'output_tokens': token_count,
            'total_tokens': token_count,
            'estimated': True
        }

    @classmethod
    def count_conversation_tokens(cls, messages: list) -> int:
        """
        Count total tokens in a conversation history.

        Args:
            messages: List of message dictionaries with 'content' key

        Returns:
            Total token count
        """
        total = 0
        for msg in messages:
            content = msg.get('content', '')
            if isinstance(content, str):
                total += cls.count_tokens(content)
            elif isinstance(content, list):
                # Handle multimodal content (text parts only)
                for part in content:
                    if isinstance(part, dict) and part.get('type') == 'text':
                        total += cls.count_tokens(part.get('text', ''))
                    elif isinstance(part, str):
                        total += cls.count_tokens(part)
        return total
