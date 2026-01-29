# Simply AI - Home Edition

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/flask-3.x-green.svg)](https://flask.palletsprojects.com/)

A unified chat interface for multiple AI providers (Gemini, OpenAI, Anthropic, xAI, LM Studio, Ollama). Designed for self-hosted personal/family use on a desktop or laptop, supporting up to 10 registered users.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [First-Time Configuration](#first-time-configuration)
- [Environment Configuration](#environment-configuration)
- [Data Storage](#data-storage)
- [Troubleshooting](#troubleshooting)
- [Security](#security-notes)
- [Contributing](#contributing)
- [License](#license)

## Features

- Multi-provider AI chat with streaming responses
- User authentication with optional 2FA
- File attachments (images, PDFs, documents)
- RAG (Retrieval-Augmented Generation) for document-based Q&A
- Child safety guardrails with age-based content filtering
- Token usage tracking
- Dark/light theme support

## Prerequisites

### For Windows Setup
- **Python 3.11** or higher installed and added to PATH
- Windows 10/11

### For Docker Setup
- **Docker Desktop** installed and running
- Windows 10/11, macOS, or Linux

## Installation

Choose one of the two installation methods below:

---

### Method 1: Windows Setup Script (Recommended for Development)

This method creates a Python virtual environment, sets up the database, runs all migrations, and creates an admin user.

**Step 1: Run the Setup Script**

Double-click `SETUP.bat` or run from Command Prompt:
```cmd
SETUP.bat
```

This script will:
1. Create a Python virtual environment (`.venv`)
2. Install all dependencies from `requirements.txt`
3. Initialize the SQLite database
4. Run all 13 database migrations
5. Prompt you to create an admin user

**Step 2: Start the Server**

Double-click `START_SERVER.bat` or run from Command Prompt:
```cmd
START_SERVER.bat
```

**Step 3: Access the Application**

Open your browser and navigate to:
```
http://localhost:8080
```

---

### Method 2: Docker (Recommended for Production)

Run the application in a Docker container for easier deployment and isolation.

**Step 1: Install Docker Desktop**

Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for your operating system. Ensure Docker Desktop is running before proceeding.

**Step 2: Start the Docker Container**

Double-click `start_docker.bat` or run from Command Prompt:
```cmd
start_docker.bat
```

This will build and start the Docker container. The first run may take a few minutes to download and build the image.

**Step 3: Access the Application**

Open your browser and navigate to:
```
http://localhost:8080
```

**Step 4: Initialize the Database (First Time Only)**

For the first run, you need to initialize the database and create an admin user:

```cmd
docker-compose exec app python scripts/setup/init_db.py
docker-compose exec app python scripts/setup/create_admin.py
```

Or use the quick admin setup (username: `admin`, password: `AdminPass123!@#`):
```cmd
docker-compose exec app python scripts/setup/quick_create_admin.py
```

**Stopping the Docker Container**

To stop the application:
```cmd
stop_docker.bat
```

**Viewing Logs**

To view application logs:
```cmd
docker-compose logs -f app
```

---

## First-Time Configuration

### 1. Log In as Admin

Use the admin credentials created during setup:
- **Quick Admin**: Username `admin`, Password `AdminPass123!@#`
- **Custom Admin**: The credentials you specified during setup

### 2. Configure API Keys

Navigate to **Settings** and configure API keys for the AI providers you want to use:

| Provider | Where to Get API Key |
|----------|---------------------|
| Google Gemini | [Google AI Studio](https://aistudio.google.com/apikey) |
| OpenAI | [OpenAI Platform](https://platform.openai.com/api-keys) |
| Anthropic | [Anthropic Console](https://console.anthropic.com/) |
| xAI (Grok) | [xAI Console](https://console.x.ai/) |

For **local models** (LM Studio, Ollama), configure the server URL instead:
- LM Studio default: `http://localhost:1234/v1` (Note! When running on Docker, replace 'localhost' with the actual IP address where LM Studio is installed. Ensure LM Studio server is configured to "Serve on local network".)
- Ollama default: `http://localhost:11434` (Note! When running on Docker, replace 'localhost' with the actual IP address where Ollama is installed. Ensure Ollama is configured to "Expose to the network".)

### 3. Additional Users

From the admin Settings page, you can manage user accounts for family members (up to 10 users total).

---

## Default Ports

| Setup Method | URL |
|--------------|-----|
| Windows (SETUP.bat) | `http://localhost:8080` |
| Docker | `http://localhost:8080` |

---

## Data Storage

| Data Type | Location |
|-----------|----------|
| Database | `instance/simplyai.db` |
| File Uploads | `uploads/` |
| Vector Store (RAG) | `data/chroma/` |
| Application Logs | `logs/` |

---

## Environment Configuration

The application uses a `.env` file for configuration. A template is provided in `.env.example`.

### Quick Setup

Copy the template to create your configuration file:
```cmd
copy .env.example .env
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `development` | Environment mode (`development` or `production`) |
| `PORT` | `8080` | Server port |
| `SECRET_KEY` | (required) | Secret key for session encryption - **generate a unique key!** |
| `DB_TYPE` | `sqlite` | Database type (sqlite recommended for home use) |
| `SESSION_COOKIE_SECURE` | `False` | Set to `True` only if using HTTPS |
| `SESSION_COOKIE_HTTPONLY` | `True` | Prevent JavaScript access to cookies |
| `PERMANENT_SESSION_LIFETIME` | `86400` | Session timeout in seconds (default: 24 hours) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Generating a Secret Key

For production use, generate a secure secret key:
```cmd
python -c "import secrets; print(secrets.token_hex(64))"
```

Copy the output and paste it as the `SECRET_KEY` value in your `.env` file.

### Important Notes

- **API keys and model IDs are NOT stored in the `.env` file.** They are configured through the admin Settings page and stored securely in the database (API keys are encrypted).
- The `SETUP.bat` script creates a default `.env` file if one doesn't exist.
- For Docker deployments, you can also use `.env.docker` as a reference.

---

## Troubleshooting

### Python not found
Ensure Python 3.11+ is installed and added to your system PATH. Verify with:
```cmd
python --version
```

### Docker container fails to start
- Ensure Docker Desktop is running
- Check if port 8080 is already in use by another application
- Try rebuilding with: `docker-compose up --build -d`

### Database errors after update
Run the database reset script (WARNING: this deletes all data):
```cmd
bat\RESET_DATABASE.bat
```

### Virtual environment issues
Recreate the virtual environment:
```cmd
rmdir /s /q .venv
SETUP.bat
```

---

## Security Notes

- Change the default admin password immediately after first login
- API keys are encrypted in the database
- Enable 2FA for additional account security
- The application is designed for local network use; do not expose to the internet without proper security measures

For security vulnerability reporting, please see [SECURITY.md](SECURITY.md).

---

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before submitting a pull request.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
