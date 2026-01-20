"""Validation utilities for user input"""

import re
from typing import Tuple, List


def validate_password(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password strength according to enterprise security standards.

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - No common patterns

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check minimum length
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    # Check for uppercase letter
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")

    # Check for lowercase letter
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")

    # Check for digit
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one number")

    # Check for common patterns
    common_patterns = [
        r'12345', r'password', r'qwerty', r'abc123', r'letmein',
        r'admin', r'welcome', r'monkey', r'dragon', r'master'
    ]

    password_lower = password.lower()
    for pattern in common_patterns:
        if pattern in password_lower:
            errors.append("Password contains common patterns and is not secure")
            break

    # Check for sequential characters
    if re.search(r'(.)\1{2,}', password):
        errors.append("Password contains too many repeating characters")

    return (len(errors) == 0, errors)


def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email format.

    Args:
        email: The email address to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return (False, "Email is required")

    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(pattern, email):
        return (False, "Invalid email format")

    if len(email) > 120:
        return (False, "Email is too long (max 120 characters)")

    return (True, "")


def validate_username(username: str) -> Tuple[bool, str]:
    """
    Validate username format.

    Requirements:
    - 3-80 characters
    - Alphanumeric, underscores, and hyphens only
    - Must start with a letter or number

    Args:
        username: The username to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return (False, "Username is required")

    if len(username) < 3:
        return (False, "Username must be at least 3 characters long")

    if len(username) > 80:
        return (False, "Username is too long (max 80 characters)")

    # Check format: alphanumeric, underscores, hyphens
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', username):
        return (False, "Username can only contain letters, numbers, underscores, and hyphens, and must start with a letter or number")

    return (True, "")


def validate_date_of_birth(dob_string: str) -> Tuple[bool, str]:
    """
    Validate date of birth for child safety features.

    Requirements:
    - Must be a valid date in YYYY-MM-DD format
    - User must be at least 4 years old (minimum age for account)
    - User cannot be older than 120 years
    - Cannot be a future date

    Args:
        dob_string: Date of birth string in YYYY-MM-DD format

    Returns:
        Tuple of (is_valid, error_message)
    """
    from datetime import date, datetime

    if not dob_string:
        return (False, "Date of birth is required")

    # Try to parse the date
    try:
        dob = datetime.strptime(dob_string, '%Y-%m-%d').date()
    except ValueError:
        return (False, "Invalid date format. Please use YYYY-MM-DD")

    today = date.today()

    # Check if date is in the future
    if dob > today:
        return (False, "Date of birth cannot be in the future")

    # Calculate age
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    # Check minimum age
    if age < 4:
        return (False, "You must be at least 4 years old to create an account")

    # Check maximum age (sanity check)
    if age > 120:
        return (False, "Please enter a valid date of birth")

    return (True, "")


def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input by removing potentially harmful characters.

    Args:
        text: The text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace('\x00', '')

    # Strip whitespace
    text = text.strip()

    # Truncate to max length
    if len(text) > max_length:
        text = text[:max_length]

    return text
