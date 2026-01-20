# Simply AI - Windows Build Guide

This folder contains all the files needed to build a Windows executable and installer for Simply AI - Home Edition.

## Prerequisites

1. **Python 3.10+** with pip
2. **Virtual environment** with all dependencies installed:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. **Inno Setup 6.x** (optional, for creating installer)
   - Download from: https://jrsoftware.org/isinfo.php
   - Install to default location

## Quick Build

Run the build script:
```bash
build\build_windows.bat
```

This will:
1. Install PyInstaller (if not present)
2. Compile the application to `dist\SimplyAI\`
3. Create an installer in `installer_output\` (if Inno Setup is installed)

## Build Output

After a successful build:

```
dist\
  SimplyAI\
    SimplyAI.exe        <- Main executable
    templates\          <- HTML templates
    static\             <- CSS, JS, images
    scripts\            <- Setup scripts (bundled)
    ... (other dependencies)

installer_output\
  SimplyAI-Setup-1.0.0.exe  <- Installer (if Inno Setup available)
```

## Testing the Build

1. Navigate to `dist\SimplyAI\`
2. Run `SimplyAI.exe`
3. On first run, the application will:
   - Create the database
   - Initialize roles and permissions
   - Create the admin user (from installer configuration)
   - Open your browser to `http://localhost:8080`

## Installer Setup

During installation, users will be prompted to:
1. **Choose a port** - The web server port (default: 8080)
2. **Create admin account** - Set their own username, email, and password

**Password Requirements:**
- Minimum 8 characters
- At least one uppercase letter (A-Z)
- At least one lowercase letter (a-z)
- At least one number (0-9)
- At least one special character (!@#$%^&*...)

The admin credentials are stored temporarily during installation and processed securely on first application startup, after which the temporary config file is deleted.

## Build Files

| File | Description |
|------|-------------|
| `simplyai.spec` | PyInstaller specification file |
| `installer.iss` | Inno Setup installer script |
| `build_windows.bat` | Automated build script |

## Manual Build Steps

If you prefer to build manually:

### Step 1: Build with PyInstaller
```bash
cd path\to\Simply_AI_Home
.venv\Scripts\activate
pip install pyinstaller
pyinstaller --clean --noconfirm build\simplyai.spec
```

### Step 2: Create Installer (optional)
1. Open `build\installer.iss` in Inno Setup Compiler
2. Click Build > Compile
3. Installer will be created in `installer_output\`

## Troubleshooting

### Build fails with missing module
```bash
pip install -r requirements.txt
```

### Antivirus blocks the build
Add an exception for the project folder in your antivirus software.

### "DLL not found" errors
Ensure you're using the virtual environment and all dependencies are installed.

### Application doesn't start
Check the console output for errors. Common issues:
- Port 8080 already in use (change PORT in .env)
- Missing write permissions in install directory

## Customization

### Change default port
Edit `run_compiled.py` and change the default port:
```python
port = int(os.environ.get('PORT', 8080))  # Change 8080 to your preferred port
```

### Change application icon
1. Create a `.ico` file (256x256 recommended)
2. Place it at `static\images\favicon.ico`
3. Update `simplyai.spec` to reference it

### Modify installer settings
Edit `installer.iss` to change:
- Application name and version
- Default installation directory
- Shortcuts and icons
- License agreement (uncomment LicenseFile line)

## Distribution

The installer (`SimplyAI-Setup-x.x.x.exe`) is a self-contained package that users can run to install Simply AI on their Windows computer. No Python installation required.

**Recommended distribution methods:**
- Direct download from your website
- GitHub Releases (binary only)
- Cloud storage (Dropbox, Google Drive, etc.)
