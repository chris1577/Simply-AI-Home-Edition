from flask import Blueprint, render_template, jsonify, request, send_from_directory, current_app
from flask_login import login_required, current_user
from app.models.chat import Chat
from app.models.user import User
from app.models.attachment import Attachment
from app import db
import os

bp = Blueprint('main', __name__)


@bp.route('/')
@login_required
def index():
    """Main chatbot interface - requires authentication"""
    from app.models.admin_settings import AdminSettings

    # Prepare user context for welcome message
    user_context = {
        'is_authenticated': True,
        'username': current_user.username,
        'full_name': current_user.full_name if hasattr(current_user, 'full_name') else None,
        'is_new_user': True,
        'is_super_admin': current_user.has_role('super_admin')
    }

    # Check if user has any previous chats (excluding deleted ones)
    chat_count = Chat.query.filter_by(
        user_id=current_user.id,
        is_deleted=False
    ).count()
    user_context['is_new_user'] = (chat_count == 0)

    # Get model IDs from AdminSettings (system-level configuration)
    model_ids = {
        'gemini': AdminSettings.get_system_model_id('gemini'),
        'openai': AdminSettings.get_system_model_id('openai'),
        'anthropic': AdminSettings.get_system_model_id('anthropic'),
        'xai': AdminSettings.get_system_model_id('xai'),
        'lm_studio': AdminSettings.get_system_model_id('lm_studio'),
        'ollama': AdminSettings.get_system_model_id('ollama')
    }

    return render_template('index.html', user_context=user_context, model_ids=model_ids)


@bp.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Enterprise AI GUI'
    }), 200


@bp.route('/api/status')
def status():
    """API status endpoint"""
    return jsonify({
        'api': 'v1',
        'status': 'operational'
    }), 200


@bp.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename):
    """Serve uploaded files - requires authentication"""
    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')

        # Get absolute path for security check
        abs_upload_folder = os.path.abspath(upload_folder)
        abs_filepath = os.path.abspath(os.path.join(upload_folder, filename))

        # Security: Prevent path traversal attacks
        if not abs_filepath.startswith(abs_upload_folder):
            return jsonify({"error": "Invalid file path"}), 403

        # Check if file exists
        if not os.path.exists(abs_filepath):
            return jsonify({"error": "File not found"}), 404

        # Get directory and filename components
        directory = os.path.dirname(filename) if os.path.dirname(filename) else ''
        file_name = os.path.basename(filename)

        # Serve the file - send_from_directory needs absolute path
        if directory:
            full_directory = os.path.abspath(os.path.join(upload_folder, directory))
            return send_from_directory(full_directory, file_name)
        else:
            abs_upload_folder_final = os.path.abspath(upload_folder)
            return send_from_directory(abs_upload_folder_final, file_name)

    except Exception as e:
        current_app.logger.error(f"Error serving file {filename}: {str(e)}")
        return jsonify({"error": "Server error"}), 500


# Backward compatibility routes - redirect to new API endpoints (all require authentication)
@bp.route('/chat', methods=['POST'])
@login_required
def chat_compat():
    """Backward compatibility: redirect to /api/chat"""
    from app.routes.chat import chat as api_chat
    return api_chat()


@bp.route('/history', methods=['GET'])
@login_required
def history_compat():
    """Backward compatibility: redirect to /api/history"""
    from app.routes.chat import get_history
    return get_history()


@bp.route('/sessions', methods=['GET'])
@login_required
def sessions_compat():
    """Backward compatibility: redirect to /api/sessions"""
    from app.routes.chat import get_sessions
    return get_sessions()


@bp.route('/delete_chat/<session_id>', methods=['DELETE'])
@login_required
def delete_chat_compat(session_id):
    """Backward compatibility: redirect to /api/delete_chat"""
    from app.routes.chat import delete_chat
    return delete_chat(session_id)


@bp.route('/config', methods=['GET', 'POST'])
@login_required
def config_compat():
    """Backward compatibility: redirect to /api/config"""
    from app.routes.chat import get_config, save_config
    if request.method == 'POST':
        return save_config()
    else:
        return get_config()


# Admin User Management Routes
@bp.route('/api/admin/users', methods=['GET'])
@login_required
def get_all_users():
    """Get all users - super_admin only"""
    # Check if current user is super_admin
    if not current_user.has_role('super_admin'):
        return jsonify({'error': 'Unauthorized. Super admin access required.'}), 403

    try:
        # Get all users except the current user (can't delete yourself)
        users = User.query.filter(User.id != current_user.id).order_by(User.created_at.desc()).all()

        users_list = []
        for user in users:
            # Count chats for each user
            chat_count = Chat.query.filter_by(user_id=user.id, is_deleted=False).count()

            users_list.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat() + 'Z' if user.created_at else None,
                'last_login': user.last_login.isoformat() + 'Z' if user.last_login else None,
                'is_active': user.is_active,
                'roles': [role.name for role in user.roles],
                'chat_count': chat_count,
                'twofa_enabled': user.twofa_enabled,
                'age_group': user.get_age_group()
            })

        return jsonify({
            'users': users_list,
            'total': len(users_list)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching users: {str(e)}")
        return jsonify({'error': 'Failed to fetch users'}), 500


@bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Delete a user and all associated data - super_admin only"""
    # Check if current user is super_admin
    if not current_user.has_role('super_admin'):
        return jsonify({'error': 'Unauthorized. Super admin access required.'}), 403

    # Prevent self-deletion
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    try:
        # Find the user to delete
        user_to_delete = User.query.get(user_id)
        if not user_to_delete:
            return jsonify({'error': 'User not found'}), 404

        # Get all chats and their associated files before deletion
        chats = Chat.query.filter_by(user_id=user_id).all()
        files_to_delete = []

        for chat in chats:
            # Get all messages in this chat
            messages = chat.messages.all()
            for message in messages:
                # Get all attachments in this message
                for attachment in message.attachments:
                    # Build full file path
                    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
                    full_path = os.path.join(upload_folder, attachment.file_path)
                    files_to_delete.append(full_path)

        # Delete the user (cascade will handle chats, messages, attachments records)
        db.session.delete(user_to_delete)
        db.session.commit()

        # Delete physical files
        deleted_files = 0
        failed_files = []
        for file_path in files_to_delete:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_files += 1
            except Exception as file_error:
                current_app.logger.warning(f"Failed to delete file {file_path}: {str(file_error)}")
                failed_files.append(file_path)

        current_app.logger.info(f"User {user_to_delete.username} (ID: {user_id}) deleted by {current_user.username}")
        current_app.logger.info(f"Deleted {deleted_files} files, {len(failed_files)} files failed to delete")

        return jsonify({
            'message': f'User {user_to_delete.username} and all associated data deleted successfully',
            'deleted_files': deleted_files,
            'failed_files': len(failed_files)
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting user {user_id}: {str(e)}")
        return jsonify({'error': f'Failed to delete user: {str(e)}'}), 500
