"""Quick admin user creation (non-interactive)"""
import os
import sys

# Add the project root directory to the path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app import create_app, db
from app.models.user import User
from app.models.rbac import Role

app = create_app('development')

with app.app_context():
    # Check if admin already exists
    existing = User.query.filter_by(username='admin').first()
    if existing:
        print(f"[INFO] Admin user already exists (ID: {existing.id})")
        sys.exit(0)

    # Create admin user
    user = User(
        username='admin',
        email='admin@example.com',
        is_admin=True
    )

    success, error = user.set_password('AdminPass123!@#', check_history=False)
    if not success:
        print(f"[ERROR] {error}")
        sys.exit(1)

    # Add to session first
    db.session.add(user)
    db.session.flush()  # Get the user ID

    # Add super_admin role
    super_admin_role = Role.query.filter_by(name='super_admin').first()
    user_role = Role.query.filter_by(name='user').first()

    if super_admin_role:
        user.add_role(super_admin_role)
    if user_role:
        user.add_role(user_role)

    db.session.commit()

    print("[OK] Admin user created successfully!")
    print(f"   Username: admin")
    print(f"   Email: admin@example.com")
    print(f"   Password: AdminPass123!@#")
    print(f"   Roles: {', '.join([role.name for role in user.roles])}")
    print(f"   User ID: {user.id}")
