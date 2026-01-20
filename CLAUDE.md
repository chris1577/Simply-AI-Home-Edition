# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Simply AI - Home Edition is a Flask-based unified chat interface for multiple AI providers (Gemini, OpenAI, Anthropic, xAI, LM Studio, Ollama). Designed for self-hosted personal/family use supporting up to 10 registered users.

## Common Commands

### Starting the Server
```bash
# Windows
START_SERVER.bat
# Or directly
python run.py
```
Server runs at `http://localhost:8080`.

### Database Operations
```bash
# Full database reset (prompts for confirmation, runs all migrations)
bat\RESET_DATABASE.bat

# Quick refresh for testing (no prompts, creates quick admin)
bat\QUICK_REFRESH.bat
# Creates admin user: admin / AdminPass123!@#

# Initialize database only
python scripts/setup/init_db.py

# Create admin user interactively
python scripts/setup/create_admin.py
```

### Running Tests
```bash
# All tests
python -m pytest

# Specific test file
python -m pytest scripts/tests/test_filename.py

# Quick smoke test (requires running server)
python scripts/tests/quick_test.py
```

### Linting and Type Checking
```bash
black app/
flake8 app/
mypy app/
```

## Architecture

### Application Structure
- **Flask Application Factory** pattern in `app/__init__.py`
- **Blueprints**: `auth` (authentication), `chat` (API), `main` (UI) in `app/routes/`
- **SQLAlchemy ORM** with SQLite default (supports SQL Server Express via `DB_TYPE=sqlexpress`)
- **Server-Sent Events (SSE)** for streaming AI responses

### Key Services (`app/services/`)
- `ai_service.py`: Unified interface for all AI providers with streaming support
- `rag_service.py`: Orchestrates document processing, embedding, and vector retrieval (ChromaDB)
- `token_service.py`: Token counting via tiktoken
- `file_service.py`: File upload handling
- `encryption_service.py`: API key encryption

### Key Models (`app/models/`)
- `User`, `Chat`, `Message`, `Attachment`: Core chat functionality
- `AdminSettings`: System-wide config (API keys, model IDs, rate limits)
- `Document`, `DocumentChunk`: RAG document storage
- `Role`, `Permission`: RBAC system

### Configuration
- Environment variables in `.env` (see `.env.example`)
- API keys and model IDs stored in database via `AdminSettings`, NOT in `.env`
- Configure via UI: Settings page (super_admin only)

## Database Migrations

Migrations are Python scripts in `scripts/migrations/`. Run them after schema changes:

```bash
python scripts/migrations/add_model_columns.py
python scripts/migrations/add_attachments_table.py
python scripts/migrations/add_model_visibility.py
python scripts/migrations/add_admin_settings.py
python scripts/migrations/add_rag_tables.py
python scripts/migrations/add_vision_settings.py
python scripts/migrations/add_date_of_birth.py
python scripts/migrations/add_child_safety_settings.py
python scripts/migrations/add_session_token.py
python scripts/migrations/add_model_id_settings.py
python scripts/migrations/add_token_tracking.py
python scripts/migrations/add_rate_limit_settings.py
python scripts/migrations/add_distilled_context.py
```

The `bat\QUICK_REFRESH.bat` script runs all migrations automatically.

## Key Implementation Patterns

### Adding a New AI Provider
1. Add provider method in `app/services/ai_service.py` (both sync and streaming versions)
2. Update `get_response()` and `get_response_stream()` dispatch methods
3. Add API key/model ID support in `AdminSettings` model
4. Add model visibility entry in `scripts/migrations/add_model_visibility.py`

### Streaming Responses
Chat responses use SSE via `stream_with_context`. Format:
```python
yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
yield f"data: {json.dumps({'type': 'done', 'full_content': full, 'usage': usage_data})}\n\n"
```

### Database Operations
Use `db.session` with explicit commits in route handlers:
```python
db.session.add(obj)
db.session.commit()
```

### Rate Limiting
Dynamic rate limits from `AdminSettings`. Decorators in routes:
```python
@limiter.limit(rate_limit_chat)
```

### Permission Checking
Use `@require_permission` decorator or `current_user.has_role('super_admin')` for admin-only routes.
