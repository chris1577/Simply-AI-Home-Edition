from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from app import db, limiter, rate_limit_login, rate_limit_register, rate_limit_2fa
from app.models.user import User
from app.utils.validators import validate_password, validate_email, validate_username, validate_date_of_birth, sanitize_input
from datetime import datetime

bp = Blueprint('auth', __name__)


# ==================== HTML Page Routes ====================

@bp.route('/profile')
@login_required
def profile_page():
    """Render user profile page"""
    return render_template('profile.html')


@bp.route('/settings')
@login_required
def settings_page():
    """Render settings page"""
    return render_template('settings.html')


# ==================== API Routes ====================


@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit(rate_limit_register)
def register():
    """Register a new user"""
    # Home Edition: Maximum 10 registered users
    MAX_USERS = 10

    # Render registration page for GET requests
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('main.index'))
        return render_template('register.html')

    # Handle registration API for POST requests
    data = request.get_json()

    # Check user limit for Home Edition
    current_user_count = User.query.count()
    if current_user_count >= MAX_USERS:
        return jsonify({
            'error': f'Maximum user limit ({MAX_USERS}) reached. This is the Home Edition which supports up to {MAX_USERS} users.'
        }), 403

    # Validate input
    username = sanitize_input(data.get('username', ''), max_length=80)
    email = sanitize_input(data.get('email', ''), max_length=120)
    password = data.get('password', '')
    date_of_birth = data.get('date_of_birth', '')

    if not username or not email or not password:
        return jsonify({'error': 'Missing required fields'}), 400

    # Validate username
    username_valid, username_error = validate_username(username)
    if not username_valid:
        return jsonify({'error': username_error}), 400

    # Validate email
    email_valid, email_error = validate_email(email)
    if not email_valid:
        return jsonify({'error': email_error}), 400

    # Validate password strength with enhanced requirements
    password_valid, password_errors = validate_password(password)
    if not password_valid:
        return jsonify({
            'error': 'Password does not meet security requirements',
            'details': password_errors
        }), 400

    # Validate date of birth (required for child safety features)
    dob_valid, dob_error = validate_date_of_birth(date_of_birth)
    if not dob_valid:
        return jsonify({'error': dob_error}), 400

    # Check if user exists
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists'}), 400

    # Parse date of birth
    parsed_dob = datetime.strptime(date_of_birth, '%Y-%m-%d').date()

    # Create user with date of birth
    user = User(username=username, email=email, date_of_birth=parsed_dob)
    success, error = user.set_password(password, check_history=False)  # No history check for new users

    if not success:
        return jsonify({'error': error}), 400

    db.session.add(user)
    db.session.commit()

    return jsonify({
        'message': 'User created successfully',
        'user': user.to_dict(include_email=True)
    }), 201


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit(rate_limit_login)
def login():
    """Login user"""
    # Render login page for GET requests
    if request.method == 'GET':
        if current_user.is_authenticated:
            return redirect(url_for('main.index'))
        return render_template('login.html')

    # Handle login API for POST requests
    data = request.get_json()

    username = sanitize_input(data.get('username', ''), max_length=80)
    password = data.get('password', '')

    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400

    # Find user
    user = User.query.filter_by(username=username).first()

    # If user doesn't exist, return generic error to prevent username enumeration
    if not user:
        return jsonify({'error': 'Invalid credentials'}), 401

    # Check if account is locked
    if user.is_account_locked():
        lockout_time = user.account_locked_until
        if lockout_time:
            minutes_remaining = int((lockout_time - datetime.utcnow()).total_seconds() / 60)
            return jsonify({
                'error': f'Account is locked due to too many failed login attempts. Please try again in {minutes_remaining} minutes.'
            }), 403

    # Check if account is disabled
    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 403

    # Verify password
    if not user.check_password(password):
        # Increment failed login attempts
        user.increment_failed_login()
        db.session.commit()

        # Check if account is now locked
        if user.is_account_locked():
            return jsonify({
                'error': 'Too many failed login attempts. Account has been locked for 15 minutes.'
            }), 403

        return jsonify({'error': 'Invalid credentials'}), 401

    # Successful password verification - reset failed attempts
    user.reset_failed_login()

    # Check if 2FA is enabled
    if user.twofa_enabled:
        # Create pending 2FA verification
        from app.models.pending_2fa import Pending2FAVerification
        token = Pending2FAVerification.create_pending_verification(user.id)

        return jsonify({
            'message': '2FA verification required',
            'requires_2fa': True,
            '2fa_token': token
        }), 200

    # No 2FA required - complete login
    user.last_login = datetime.utcnow()
    # Generate new session token for single-session enforcement
    session_token = user.generate_session_token()
    login_user(user, remember=True)
    # Store session token in Flask session for validation
    session['session_token'] = session_token
    db.session.commit()

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(include_email=True)
    }), 200


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    # Invalidate session token
    current_user.invalidate_session()
    db.session.commit()
    # Clear session token from Flask session
    session.pop('session_token', None)
    logout_user()
    return jsonify({'message': 'Logout successful'}), 200


@bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current logged-in user"""
    return jsonify({
        'user': current_user.to_dict(include_email=True),
        'is_super_admin': current_user.has_role('super_admin')
    }), 200


@bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    data = request.get_json()

    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'error': 'Missing required fields'}), 400

    # Verify current password
    if not current_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 401

    # Validate new password with enhanced requirements
    password_valid, password_errors = validate_password(new_password)
    if not password_valid:
        return jsonify({
            'error': 'New password does not meet security requirements',
            'details': password_errors
        }), 400

    # Update password with history check
    success, error = current_user.set_password(new_password, check_history=True)

    if not success:
        return jsonify({'error': error}), 400

    db.session.commit()

    return jsonify({'message': 'Password changed successfully'}), 200


# ==================== 2FA Verification During Login ====================

@bp.route('/verify-2fa', methods=['POST'])
@limiter.limit(rate_limit_2fa)
def verify_2fa():
    """Verify 2FA code and complete login"""
    from app.services.twofa_service import TwoFAService
    from app.models.pending_2fa import Pending2FAVerification

    data = request.get_json()
    token = data.get('2fa_token', '')
    code = data.get('code', '')
    use_backup = data.get('use_backup_code', False)

    if not token or not code:
        return jsonify({'error': 'Missing 2FA token or code'}), 400

    # Verify the pending 2FA token
    pending = Pending2FAVerification.verify_token(token)

    if not pending:
        return jsonify({'error': 'Invalid or expired 2FA token'}), 401

    # Get user
    user = User.query.get(pending.user_id)

    if not user or not user.is_active:
        return jsonify({'error': 'User not found or inactive'}), 401

    # Verify the 2FA code
    code_valid = False

    if use_backup:
        # Verify backup code
        code_valid = TwoFAService.verify_backup_code(user, code)
    else:
        # Verify TOTP code
        code_valid = TwoFAService.verify_totp_code(user, code)

    if not code_valid:
        return jsonify({'error': 'Invalid 2FA code'}), 401

    # Mark pending verification as complete
    Pending2FAVerification.mark_verified(token)

    # Complete login
    user.last_login = datetime.utcnow()
    # Generate new session token for single-session enforcement
    session_token = user.generate_session_token()
    login_user(user, remember=True)
    # Store session token in Flask session for validation
    session['session_token'] = session_token
    db.session.commit()

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(include_email=True)
    }), 200


# ==================== 2FA Management Endpoints ====================

@bp.route('/2fa/enroll', methods=['POST'])
@login_required
def enroll_2fa():
    """Start 2FA enrollment process"""
    from app.services.twofa_service import TwoFAService

    user = current_user

    if user.twofa_enabled:
        return jsonify({'error': '2FA is already enabled for this account'}), 400

    # Generate secret and QR code (but don't enable yet)
    secret = TwoFAService.generate_secret()
    user.twofa_secret = secret
    db.session.commit()

    qr_code = TwoFAService.generate_qr_code(user)

    return jsonify({
        'message': '2FA enrollment started',
        'secret': secret,
        'qr_code': qr_code,
        'instructions': 'Scan the QR code with your authenticator app, then verify with a code to complete setup'
    }), 200


@bp.route('/2fa/verify-enrollment', methods=['POST'])
@login_required
def verify_2fa_enrollment():
    """Complete 2FA enrollment by verifying a code"""
    from app.services.twofa_service import TwoFAService

    user = current_user
    data = request.get_json()
    code = data.get('code', '')

    if user.twofa_enabled:
        return jsonify({'error': '2FA is already enabled'}), 400

    if not user.twofa_secret:
        return jsonify({'error': 'Please start 2FA enrollment first'}), 400

    # Verify the code
    if not TwoFAService.verify_totp_code(user, code):
        return jsonify({'error': 'Invalid verification code'}), 400

    # Generate backup codes
    backup_codes = TwoFAService.generate_backup_codes()

    # Store backup codes
    from app.models.twofa_backup import TwoFABackupCode
    TwoFABackupCode.create_backup_codes(user.id, backup_codes)

    # Enable 2FA
    user.twofa_enabled = True
    db.session.commit()

    return jsonify({
        'message': '2FA enabled successfully',
        'backup_codes': backup_codes,
        'warning': 'Save these backup codes in a secure place. They can be used if you lose access to your authenticator app.'
    }), 200


@bp.route('/2fa/disable', methods=['POST'])
@login_required
def disable_2fa():
    """Disable 2FA for the current user"""
    from app.services.twofa_service import TwoFAService

    user = current_user
    data = request.get_json()
    password = data.get('password', '')

    if not user.twofa_enabled:
        return jsonify({'error': '2FA is not enabled'}), 400

    # Verify password for security
    if not user.check_password(password):
        return jsonify({'error': 'Invalid password'}), 401

    # Disable 2FA
    TwoFAService.disable_2fa_for_user(user)

    return jsonify({'message': '2FA has been disabled'}), 200


@bp.route('/2fa/regenerate-backup-codes', methods=['POST'])
@login_required
def regenerate_backup_codes():
    """Regenerate backup codes"""
    from app.services.twofa_service import TwoFAService

    user = current_user
    data = request.get_json()
    code = data.get('code', '')

    if not user.twofa_enabled:
        return jsonify({'error': '2FA is not enabled'}), 400

    # Verify current 2FA code
    if not TwoFAService.verify_totp_code(user, code):
        return jsonify({'error': 'Invalid verification code'}), 400

    # Generate new backup codes
    backup_codes = TwoFAService.regenerate_backup_codes(user)

    return jsonify({
        'message': 'Backup codes regenerated successfully',
        'backup_codes': backup_codes,
        'warning': 'Old backup codes are no longer valid'
    }), 200


@bp.route('/2fa/status', methods=['GET'])
@login_required
def get_2fa_status():
    """Get 2FA status for current user"""
    from app.services.twofa_service import TwoFAService

    user = current_user

    status = {
        'enabled': user.twofa_enabled,
        'backup_codes_remaining': 0
    }

    if user.twofa_enabled:
        status['backup_codes_remaining'] = TwoFAService.get_remaining_backup_codes(user)

    return jsonify(status), 200


# ==================== User Settings Routes ====================


@bp.route('/settings/data', methods=['GET'])
@login_required
def get_settings():
    """Get user settings (JSON API)"""
    from app.models.user_settings import UserSettings

    settings = UserSettings.get_or_create(current_user.id)

    return jsonify(settings.to_dict()), 200


@bp.route('/settings', methods=['POST'])
@login_required
def save_settings():
    """Save user settings"""
    from app.models.user_settings import UserSettings

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        settings = UserSettings.get_or_create(current_user.id)
        settings.update_from_dict(data)
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Settings saved successfully',
            'settings': settings.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'error': f'Failed to save settings: {str(e)}'
        }), 500
