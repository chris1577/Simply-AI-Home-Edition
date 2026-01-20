"""Role-Based Access Control (RBAC) Models"""

from app import db
from datetime import datetime


# Association tables for many-to-many relationships
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)

role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)


class Role(db.Model):
    """
    User roles for access control.
    Home Edition: super_admin > user
    """

    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    level = db.Column(db.Integer, nullable=False)  # Higher level = more permissions
    is_system_role = db.Column(db.Boolean, default=False)  # System roles can't be deleted

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    permissions = db.relationship('Permission', secondary=role_permissions,
                                 back_populates='roles', lazy='dynamic')

    def __repr__(self):
        return f'<Role {self.name}>'

    @staticmethod
    def get_role_hierarchy():
        """
        Return role hierarchy levels.
        Home Edition: Simplified to super_admin and user only.
        """
        return {
            'super_admin': 100,
            'user': 40
        }

    @staticmethod
    def initialize_system_roles():
        """
        Initialize default system roles.
        Should be called once during application setup.
        Home Edition: Only super_admin and user roles.
        """
        hierarchy = Role.get_role_hierarchy()

        default_roles = [
            {
                'name': 'super_admin',
                'description': 'Administrator with full system access',
                'level': hierarchy['super_admin'],
                'is_system_role': True
            },
            {
                'name': 'user',
                'description': 'Standard user',
                'level': hierarchy['user'],
                'is_system_role': True
            }
        ]

        for role_data in default_roles:
            existing_role = Role.query.filter_by(name=role_data['name']).first()
            if not existing_role:
                role = Role(**role_data)
                db.session.add(role)

        db.session.commit()

    def has_permission(self, permission_name: str) -> bool:
        """
        Check if this role has a specific permission.

        Args:
            permission_name: Name of the permission

        Returns:
            True if role has permission, False otherwise
        """
        return self.permissions.filter_by(name=permission_name).first() is not None

    def add_permission(self, permission):
        """Add a permission to this role"""
        if not self.has_permission(permission.name):
            self.permissions.append(permission)

    def remove_permission(self, permission):
        """Remove a permission from this role"""
        if self.has_permission(permission.name):
            self.permissions.remove(permission)


class Permission(db.Model):
    """
    Permissions that can be assigned to roles.
    """

    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    resource = db.Column(db.String(50), nullable=False)  # e.g., 'user', 'project', 'chat'
    action = db.Column(db.String(50), nullable=False)  # e.g., 'create', 'read', 'update', 'delete'

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    roles = db.relationship('Role', secondary=role_permissions,
                           back_populates='permissions', lazy='dynamic')

    def __repr__(self):
        return f'<Permission {self.name}>'

    @staticmethod
    def initialize_system_permissions():
        """
        Initialize default system permissions.
        Home Edition: Simplified permissions for user and chat management.
        """
        default_permissions = [
            # User permissions
            {'name': 'user.create', 'resource': 'user', 'action': 'create', 'description': 'Create new users'},
            {'name': 'user.read', 'resource': 'user', 'action': 'read', 'description': 'View users'},
            {'name': 'user.update', 'resource': 'user', 'action': 'update', 'description': 'Update users'},
            {'name': 'user.delete', 'resource': 'user', 'action': 'delete', 'description': 'Delete users'},

            # Chat permissions
            {'name': 'chat.create', 'resource': 'chat', 'action': 'create', 'description': 'Create chats'},
            {'name': 'chat.read', 'resource': 'chat', 'action': 'read', 'description': 'View chats'},
            {'name': 'chat.update', 'resource': 'chat', 'action': 'update', 'description': 'Update chats'},
            {'name': 'chat.delete', 'resource': 'chat', 'action': 'delete', 'description': 'Delete chats'},

            # Admin permissions
            {'name': 'admin.access', 'resource': 'admin', 'action': 'access', 'description': 'Access admin panel'},
            {'name': 'admin.config', 'resource': 'admin', 'action': 'config', 'description': 'Modify system configuration'},
        ]

        for perm_data in default_permissions:
            existing_perm = Permission.query.filter_by(name=perm_data['name']).first()
            if not existing_perm:
                permission = Permission(**perm_data)
                db.session.add(permission)

        db.session.commit()

    @staticmethod
    def assign_default_permissions_to_roles():
        """
        Assign default permissions to system roles.
        Home Edition: super_admin gets all, user gets chat permissions.
        """
        # Get all permissions
        all_permissions = Permission.query.all()

        # Super Admin - all permissions
        super_admin = Role.query.filter_by(name='super_admin').first()
        if super_admin:
            for perm in all_permissions:
                super_admin.add_permission(perm)

        # User - chat permissions only
        user_role = Role.query.filter_by(name='user').first()
        if user_role:
            user_permissions = Permission.query.filter(
                Permission.resource == 'chat'
            ).all()
            for perm in user_permissions:
                user_role.add_permission(perm)

        db.session.commit()
