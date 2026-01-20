"""
Test script for sensitive information filter.

This script tests the filter with various sensitive data patterns.
"""

import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app.services.sensitive_info_filter import SensitiveInfoFilter


def test_filter():
    """Test various sensitive information patterns"""

    print("=" * 80)
    print("SENSITIVE INFORMATION FILTER - TEST SUITE")
    print("=" * 80)

    test_cases = [
        # API Keys
        ("My OpenAI key is sk-proj-abc123def456ghi789jkl012mno345pqr678stu901",
         "API Key detection"),

        ("Here's my Anthropic key: sk-ant-api03-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-1234567890abcdefgh",
         "Anthropic Key"),

        ("Use this Google API key: AIzaSyB1234567890abcdefghijklmnopqrs",
         "Google API Key"),

        # AWS Credentials
        ("AWS access key: AKIAIOSFODNN7EXAMPLE",
         "AWS Access Key"),

        ("aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
         "AWS Secret Key"),

        # JWT Token
        ("Authorization token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
         "JWT Token"),

        # Passwords
        ("My password is SuperSecret123!",
         "Password phrase"),

        ("password=MyP@ssw0rd123",
         "Password assignment"),

        # Credit Card
        ("My card number is 4532-1234-5678-9010",
         "Credit Card"),

        # SSN
        ("Social Security: 123-45-6789",
         "Social Security Number"),

        # Database Connection
        ("postgres://admin:MySecretPass@localhost:5432/mydb",
         "Database Connection String"),

        # Private Key
        ("""Here's the key:
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890abcdef...
-----END RSA PRIVATE KEY-----""",
         "Private Key"),

        # Safe content (should NOT be filtered)
        ("How do I reset my password?",
         "Safe question about passwords"),

        ("Please send me the API documentation",
         "Safe API reference"),

        ("What's your email address?",
         "Safe email question"),
    ]

    print("\nTesting filter with various inputs:\n")

    for i, (input_text, description) in enumerate(test_cases, 1):
        print(f"Test {i}: {description}")
        print(f"Input: {input_text[:100]}..." if len(input_text) > 100 else f"Input: {input_text}")

        filtered_text = SensitiveInfoFilter.filter_message(input_text)
        has_sensitive = SensitiveInfoFilter.has_sensitive_info(input_text)

        if filtered_text != input_text:
            print(f"Filtered: {filtered_text[:100]}..." if len(filtered_text) > 100 else f"Filtered: {filtered_text}")
            print(f"Status: REDACTED (contained sensitive info)")
        else:
            print(f"Status: CLEAN (no sensitive info detected)")

        print(f"Has sensitive info: {has_sensitive}")
        print("-" * 80)

    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETED")
    print("=" * 80)


if __name__ == '__main__':
    test_filter()
