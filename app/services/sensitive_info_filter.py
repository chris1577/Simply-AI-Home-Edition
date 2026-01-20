"""Sensitive Information Filter Service"""

import re
from typing import List, Tuple


class SensitiveInfoFilter:
    """
    Service for detecting and filtering sensitive information from text.

    This filter is designed to strike a balance between security and utility:
    - It catches obvious sensitive patterns (API keys, tokens, credentials)
    - It's context-aware for passwords (filters values, not just the word)
    - It preserves legitimate information that users need to share
    """

    # Regex patterns for detecting sensitive information
    # Each pattern is a tuple of (regex, replacement)
    # Replacement can be a string or a callable that takes a match object
    PATTERNS = {
        # =====================
        # API Keys and Tokens
        # =====================

        # Anthropic API keys: sk-ant-api*-* (must be checked BEFORE OpenAI)
        # Note: Order matters - this must come before openai_key to avoid false matches
        'anthropic_key': (
            r'\b(sk-ant-(?:api\d+-)?[a-zA-Z0-9\-_]{20,})\b',
            '[ANTHROPIC_KEY_REDACTED]'
        ),

        # OpenAI API keys: sk-proj-*, sk-svcacct-*, sk-* (legacy)
        # Modern keys are 51+ chars, legacy were shorter
        # Negative lookahead to avoid matching Anthropic keys (sk-ant-*)
        'openai_key': (
            r'\b(sk-(?!ant-)(?:proj-|svcacct-)?[a-zA-Z0-9\-_]{20,})\b',
            '[OPENAI_KEY_REDACTED]'
        ),

        # Google API keys: AIza* (exactly 39 chars total)
        'google_api_key': (
            r'\b(AIza[a-zA-Z0-9\-_]{35})\b',
            '[GOOGLE_KEY_REDACTED]'
        ),

        # AWS Access Key ID: AKIA* (exactly 20 chars)
        'aws_access_key': (
            r'\b(AKIA[0-9A-Z]{16})\b',
            '[AWS_ACCESS_KEY_REDACTED]'
        ),

        # AWS Secret Access Key (context-aware, preserves label)
        'aws_secret_key': (
            r'(aws_secret_access_key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9/+=]{40})(["\']?)',
            lambda m: f'{m.group(1)}[AWS_SECRET_REDACTED]{m.group(3)}'
        ),

        # GitHub tokens: ghp_ (personal), ghs_ (server), gho_ (OAuth), ghr_ (refresh)
        'github_token': (
            r'\b(gh[psro]_[a-zA-Z0-9]{36,})\b',
            '[GITHUB_TOKEN_REDACTED]'
        ),

        # XAI/Grok API keys: xai-*
        'xai_key': (
            r'\b(xai-[a-zA-Z0-9\-_]{20,})\b',
            '[XAI_KEY_REDACTED]'
        ),

        # Generic API key assignment (with or without quotes)
        'generic_api_key': (
            r'(api[_-]?key\s*[:=]\s*["\']?)([a-zA-Z0-9\-_]{20,})(["\']?)',
            lambda m: f'{m.group(1)}[API_KEY_REDACTED]{m.group(3)}'
        ),

        # Bearer tokens in Authorization headers
        'bearer_token': (
            r'(\b[Bb]earer\s+)([a-zA-Z0-9\-_\.]{20,})\b',
            lambda m: f'{m.group(1)}[TOKEN_REDACTED]'
        ),

        # =====================
        # JWT Tokens
        # =====================

        # JWT format: base64url.base64url.base64url (header.payload.signature)
        'jwt_token': (
            r'\beyJ[a-zA-Z0-9\-_=]+\.eyJ[a-zA-Z0-9\-_=]+\.[a-zA-Z0-9\-_=]+\b',
            '[JWT_REDACTED]'
        ),

        # =====================
        # Private Keys
        # =====================

        # PEM format private keys (RSA, EC, DSA, ED25519, OPENSSH, ENCRYPTED)
        'private_key': (
            r'-----BEGIN (?:RSA |EC |DSA |ED25519 |OPENSSH |ENCRYPTED )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |ED25519 |OPENSSH |ENCRYPTED )?PRIVATE KEY-----',
            '[PRIVATE_KEY_REDACTED]'
        ),

        # =====================
        # Database Connection Strings
        # =====================

        # Database URLs with embedded passwords
        # Supports: postgres, postgresql, mysql, mariadb, mongodb, redis, mssql, sqlserver
        'db_connection': (
            r'((?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|mssql|sqlserver)://[^:]+:)([^@]+)(@[^\s]+)',
            lambda m: f'{m.group(1)}[PASSWORD_REDACTED]{m.group(3)}'
        ),

        # =====================
        # Password patterns (context-aware)
        # =====================

        # Password in assignment: password=*, passwd:*, pwd="*"
        'password_assignment': (
            r'(?i)((?:password|passwd|pwd)\s*[:=]\s*["\']?)([^\s"\']{6,})(["\']?)',
            lambda m: f'{m.group(1)}[PASSWORD_REDACTED]{m.group(3)}'
        ),

        # Natural language: "my password is *", "the password is *"
        'password_phrase': (
            r'(?i)((?:my |the )?password is\s+)([^\s]{6,})',
            lambda m: f'{m.group(1)}[PASSWORD_REDACTED]'
        ),

        # =====================
        # Financial / PII
        # =====================

        # Credit Card Numbers (16 digits, common formats)
        # Matches: 1234567890123456, 1234-5678-9012-3456, 1234 5678 9012 3456
        'credit_card': (
            r'\b([3-6]\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4})\b',
            '[CARD_REDACTED]'
        ),

        # Social Security Numbers (US) - multiple formats
        # Matches: 123-45-6789, 123 45 6789, 123456789
        'ssn': (
            r'\b(\d{3}[-\s]?\d{2}[-\s]?\d{4})\b',
            '[SSN_REDACTED]'
        ),

        # South African ID Numbers (13 digits) - context-aware
        # Matches: "Identity Number: 7602144059089", "ID Number: 7602144059089", "ID No: 7602144059089"
        'sa_id_number': (
            r'(?i)((?:identity\s*(?:number|no)|id\s*(?:number|no))\s*[:]\s*)(\d{13})\b',
            lambda m: f'{m.group(1)}[ID_REDACTED]'
        ),

        # =====================
        # URLs with Credentials
        # =====================

        # HTTP(S) URLs with embedded credentials (username:password@host)
        # Careful not to match port numbers - requires @ after password
        'url_with_password': (
            r'(https?://[a-zA-Z0-9._-]+:)([^@\s]+)(@[^\s]+)',
            lambda m: f'{m.group(1)}[PASSWORD_REDACTED]{m.group(3)}'
        ),

        # =====================
        # Generic Secrets
        # =====================

        # Secret/token assignment (requires quotes to reduce false positives)
        'secret_assignment': (
            r'(?i)((?:secret|client_secret|app_secret|api_secret)\s*[:=]\s*["\'])([a-zA-Z0-9\-_]{16,})(["\'])',
            lambda m: f'{m.group(1)}[SECRET_REDACTED]{m.group(3)}'
        ),

        # Environment variable style: SOME_SECRET=value, SOME_TOKEN=value
        'env_secret': (
            r'([A-Z_]*(?:SECRET|TOKEN|PASSWORD|API_KEY)[A-Z_]*\s*=\s*["\']?)([a-zA-Z0-9\-_/+=]{16,})(["\']?)',
            lambda m: f'{m.group(1)}[REDACTED]{m.group(3)}'
        ),
    }

    @staticmethod
    def filter_text(text: str, verbose: bool = False) -> Tuple[str, List[str]]:
        """
        Filter sensitive information from text.

        Args:
            text: The text to filter
            verbose: If True, return list of detected patterns

        Returns:
            Tuple of (filtered_text, list_of_detected_patterns)
        """
        if not text or not isinstance(text, str):
            return text, []

        filtered_text = text
        detected_patterns = []

        for pattern_name, (pattern, replacement) in SensitiveInfoFilter.PATTERNS.items():
            matches = re.finditer(pattern, filtered_text, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                # Track what we detected
                if verbose:
                    detected_patterns.append(pattern_name)

                # Apply replacement
                if callable(replacement):
                    # Custom replacement function
                    filtered_text = re.sub(pattern, replacement, filtered_text, flags=re.IGNORECASE | re.MULTILINE)
                else:
                    # Simple string replacement
                    filtered_text = filtered_text.replace(match.group(0), replacement)

        return filtered_text, detected_patterns

    @staticmethod
    def filter_message(message_content: str) -> str:
        """
        Filter sensitive information from a chat message.

        This is the main entry point for message filtering.

        Args:
            message_content: The message to filter

        Returns:
            Filtered message content
        """
        filtered_text, _ = SensitiveInfoFilter.filter_text(message_content, verbose=False)
        return filtered_text

    @staticmethod
    def has_sensitive_info(text: str) -> bool:
        """
        Check if text contains sensitive information without modifying it.

        Args:
            text: The text to check

        Returns:
            True if sensitive info detected, False otherwise
        """
        if not text or not isinstance(text, str):
            return False

        for pattern_name, (pattern, _) in SensitiveInfoFilter.PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
                return True

        return False

    @staticmethod
    def get_detected_patterns(text: str) -> List[str]:
        """
        Get list of detected sensitive information patterns.

        Args:
            text: The text to analyze

        Returns:
            List of pattern names that were detected
        """
        _, detected_patterns = SensitiveInfoFilter.filter_text(text, verbose=True)
        return list(set(detected_patterns))  # Remove duplicates
