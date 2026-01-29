# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Instead, please email the maintainer directly or use GitHub's private vulnerability reporting feature
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- Acknowledgment of your report within 48 hours
- Regular updates on the progress
- Credit in the security advisory (unless you prefer to remain anonymous)

## Security Best Practices for Users

### API Keys
- Never commit API keys to version control
- Use the admin Settings page to configure API keys (they are encrypted in the database)
- Rotate API keys periodically

### Deployment
- This application is designed for **local network use only**
- Do not expose to the public internet without proper security measures:
  - Use a reverse proxy (nginx, Caddy) with HTTPS
  - Implement proper firewall rules
  - Consider VPN access for remote use

### Authentication
- Change the default admin password immediately after setup
- Enable two-factor authentication (2FA) for all users
- Use strong, unique passwords

### Environment
- Generate a unique `SECRET_KEY` for production deployments
- Set `SESSION_COOKIE_SECURE=True` when using HTTPS
- Keep Python and dependencies updated

## Known Security Features

- API keys encrypted at rest using Fernet encryption
- Password hashing with Werkzeug's secure defaults
- CSRF protection via Flask-WTF
- Session security with configurable cookie settings
- Optional two-factor authentication (TOTP)
- Rate limiting on sensitive endpoints
- Child safety guardrails with age-based content filtering
