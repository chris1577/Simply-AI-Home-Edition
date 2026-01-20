"""Custom decorators for authentication and authorization"""

from functools import wraps
from flask import request, jsonify
from flask_login import current_user


def admin_required(fn):
    """
    Decorator to require admin role.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401

        if not current_user.is_admin:
            return jsonify({'error': 'Admin privileges required'}), 403

        return fn(*args, **kwargs)

    return wrapper


def require_role(role: str):
    """
    Decorator factory to require specific role.
    Usage: @require_role('admin') or @require_role('super_admin')

    Args:
        role: The required role name
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401

            # Check if user has the required role
            if not current_user.has_role(role):
                return jsonify({'error': f'Role "{role}" required'}), 403

            return fn(*args, **kwargs)

        return wrapper
    return decorator


def require_permission(permission: str):
    """
    Decorator factory to require specific permission.
    Usage: @require_permission('user.create') or @require_permission('chat.delete')

    Args:
        permission: The required permission name
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401

            # Check if user has the required permission
            if not current_user.has_permission(permission):
                return jsonify({
                    'error': f'Permission "{permission}" required',
                    'required_permission': permission
                }), 403

            return fn(*args, **kwargs)

        return wrapper
    return decorator
