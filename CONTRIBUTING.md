# Contributing to Simply AI - Home Edition

Thank you for your interest in contributing to Simply AI! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Set up the development environment using `SETUP.bat` (Windows) or Docker
4. Create a new branch for your feature or fix

## Development Setup

### Prerequisites
- Python 3.11 or higher
- Git

### Local Development
```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/Simply_AI_Home.git
cd Simply_AI_Home

# Run setup (Windows)
SETUP.bat

# Or manually create virtual environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Initialize database
python scripts/setup/init_db.py
python scripts/setup/create_admin.py

# Start the server
python run.py
```

## Making Changes

### Code Style
- Follow PEP 8 guidelines for Python code
- Use meaningful variable and function names
- Add docstrings for new functions and classes
- Keep functions focused and concise

### Commit Messages
- Use clear, descriptive commit messages
- Start with a verb in present tense (e.g., "Add", "Fix", "Update")
- Reference issue numbers when applicable

Example:
```
Add rate limiting for chat endpoints

- Implement dynamic rate limits from AdminSettings
- Add rate limit decorator to chat routes
- Update documentation

Fixes #123
```

### Testing
- Add tests for new functionality when applicable
- Ensure existing tests pass before submitting
- Run tests with: `python -m pytest`

## Pull Request Process

1. Update documentation if needed
2. Ensure your code follows the project's style guidelines
3. Test your changes thoroughly
4. Create a pull request with a clear description of changes
5. Link any related issues

### PR Title Format
- `feat: Add new feature description`
- `fix: Fix bug description`
- `docs: Update documentation`
- `refactor: Refactor component name`

## Reporting Issues

### Bug Reports
Please include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, browser)
- Screenshots if applicable

### Feature Requests
Please include:
- Clear description of the feature
- Use case and motivation
- Any implementation ideas (optional)

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Questions?

Feel free to open an issue for any questions about contributing.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
