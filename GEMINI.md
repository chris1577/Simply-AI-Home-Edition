# Simply AI - Home Edition

## Project Overview
**Simply AI - Home Edition** is a Flask-based web application providing a unified chat interface for multiple AI providers (Gemini, OpenAI, Anthropic, xAI, LM Studio, Ollama). It is designed for self-hosted personal/family use (up to 10 users).

### Key Features
*   **Multi-Provider Support:** Seamlessly switch between cloud and local AI models.
*   **RAG (Retrieval-Augmented Generation):** Upload documents (PDF, DOCX, etc.) for context-aware chat.
*   **Security:** User authentication, 2FA, session management, and sensitive info filtering.
*   **Child Safety:** Age-based guardrails with automatic system prompt injection.
*   **Token Tracking:** Real-time token usage display (input/output) and history.
*   **Architecture:** Flask Application Factory pattern, SQLAlchemy ORM, Server-Sent Events (SSE) for streaming.

## Architecture & Codebase

### Directory Structure
*   `app/`
    *   `__init__.py`: Application factory, initializes extensions (DB, Login, Limiter).
    *   `config.py`: Configuration classes (Development, Testing, Production).
    *   `models/`: SQLAlchemy models (`User`, `Chat`, `Message`, `AdminSettings`, `Document`, etc.).
    *   `routes/`: Blueprints for `auth`, `chat` (API), and `main` (UI).
    *   `services/`: Business logic isolation (`AIService`, `RAGService`, `TokenService`, `FileService`).
    *   `utils/`: Helper functions and decorators.
*   `scripts/`
    *   `migrations/`: Database migration scripts (Python).
    *   `setup/`: Setup and initialization scripts.
    *   `tests/`: Test suite (`pytest`).
*   `instance/`: Contains the SQLite database (`simplyai.db`).
*   `bat/`: Windows batch scripts for common development tasks.

### Key Components
*   **AI Service (`app/services/ai_service.py`)**: Unified interface for all AI providers. Handles streaming responses via SSE and multimodal inputs.
*   **RAG Service (`app/services/rag_service.py`)**: Orchestrates document processing, embedding generation, and vector retrieval (ChromaDB).
*   **Token Service (`app/services/token_service.py`)**: Handles token counting (via `tiktoken`) and extraction from provider APIs.
*   **Admin Settings (`app/models/admin_settings.py`)**: Stores system-wide config (API keys, model IDs, rate limits) in the database.

## Development & Usage

### Running the Application
*   **Start Server:** `start_server.bat` (Windows) or `python run.py`
    *   Default URL: `http://localhost:8080`
*   **Docker:** `start_docker.bat` / `stop_docker.bat`

### Database Management
*   **Reset Database:** `bat\RESET_DATABASE.bat` (Full reset: drops DB, runs migrations).
*   **Quick Refresh:** `bat\QUICK_REFRESH.bat` (Resets DB, creates admin, ready for testing).
*   **Migrations:** Located in `scripts/migrations/`. Run manually via `python scripts/migrations/<script_name>.py`.

### Testing
*   **Run All Tests:** `python -m pytest`
*   **Specific Test:** `python -m pytest scripts/tests/test_filename.py`

### Configuration
*   **Environment Variables:** Defined in `.env`. See `.env.example`.
    *   `FLASK_ENV`, `SECRET_KEY`, `DB_TYPE` (default: sqlite).
*   **API Keys & Models:** **NOT** in `.env`. Managed via the UI: **Settings > System API Keys** (Super Admin only).

## Coding Conventions
*   **Style:** Follow PEP 8.
*   **Imports:** Use absolute imports (e.g., `from app.models.user import User`).
*   **Database:** Use `db.session` for operations. Commit changes explicitly within route handlers.
*   **Async/Streaming:** Chat responses use `stream_with_context` for Server-Sent Events.
*   **Safety:** Always consider user permissions (`@require_permission`) and data validation.
