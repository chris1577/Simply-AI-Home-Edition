"""
Test script for admin user management feature
Tests:
1. Super admin can view users list
2. Super admin can delete users
3. Non-admin users cannot access admin routes
4. Cascade deletion works (chats, messages, attachments)
"""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from app.models.user import User
from app.models.chat import Chat, Message
from app.models.attachment import Attachment
from app.models.rbac import Role
from flask import url_for


def test_admin_user_management():
    """Test admin user management functionality"""
    app = create_app('testing')

    with app.app_context():
        # Clean up database
        db.drop_all()
        db.create_all()

        # Initialize roles
        Role.initialize_system_roles()
        db.session.commit()

        # Create super admin user
        super_admin_role = Role.query.filter_by(name='super_admin').first()
        admin_user = User(username='admin', email='admin@test.com')
        admin_user.set_password('Test123!@#')
        db.session.add(admin_user)
        db.session.flush()  # Flush to bind to session
        admin_user.add_role(super_admin_role)

        # Create regular user
        user_role = Role.query.filter_by(name='user').first()
        regular_user = User(username='testuser', email='test@test.com')
        regular_user.set_password('Test123!@#')
        db.session.add(regular_user)
        db.session.flush()  # Flush to bind to session
        regular_user.add_role(user_role)

        # Create another test user with chat history
        test_user2 = User(username='testuser2', email='test2@test.com')
        test_user2.set_password('Test123!@#')
        db.session.add(test_user2)
        db.session.flush()  # Flush to bind to session
        test_user2.add_role(user_role)
        db.session.commit()

        # Create chat for test_user2
        chat = Chat(
            name='Test Chat',
            user_id=test_user2.id,
            model_provider='gemini'
        )
        db.session.add(chat)
        db.session.commit()

        # Create messages for the chat
        message1 = Message(
            chat_id=chat.id,
            role='user',
            content='Hello'
        )
        message2 = Message(
            chat_id=chat.id,
            role='assistant',
            content='Hi there!'
        )
        db.session.add(message1)
        db.session.add(message2)
        db.session.commit()

        print("[PASS] Test data created successfully")
        print(f"  - Super admin: {admin_user.username}")
        print(f"  - Regular user 1: {regular_user.username}")
        print(f"  - Regular user 2: {test_user2.username} (with {chat.messages.count()} messages)")

        # Test 1: Check if super admin can access user list
        with app.test_client() as client:
            # Login as admin
            response = client.post('/auth/login',
                json={
                    'username': 'admin',
                    'password': 'Test123!@#'
                },
                follow_redirects=True)

            if response.status_code != 200:
                print(f"Login failed with status {response.status_code}")
                print(f"Response data: {response.data.decode()}")
            assert response.status_code == 200, f"Admin login failed with status {response.status_code}"
            print("\n[PASS] Test 1: Admin logged in successfully")

            # Get users list
            response = client.get('/api/admin/users')
            assert response.status_code == 200, "Failed to get users list"

            data = response.get_json()
            assert 'users' in data, "Response missing 'users' key"
            assert len(data['users']) == 2, f"Expected 2 users (excluding admin), got {len(data['users'])}"

            print(f"[PASS] Test 2: Admin can view users list ({data['total']} users)")

        # Test 3: Check if regular user cannot access admin routes
        with app.test_client() as client:
            # Login as regular user
            response = client.post('/auth/login',
                json={
                    'username': 'testuser',
                    'password': 'Test123!@#'
                },
                follow_redirects=True)

            assert response.status_code == 200, "Regular user login failed"

            # Try to get users list
            response = client.get('/api/admin/users')
            assert response.status_code == 403, "Regular user should not have access"

            print("[PASS] Test 3: Regular user correctly denied access to admin routes")

        # Test 4: Check cascade deletion
        with app.test_client() as client:
            # Login as admin
            client.post('/auth/login',
                json={
                    'username': 'admin',
                    'password': 'Test123!@#'
                },
                follow_redirects=True)

            # Count before deletion
            user_count_before = User.query.count()
            chat_count_before = Chat.query.count()
            message_count_before = Message.query.count()

            print(f"\n[INFO] Before deletion:")
            print(f"  - Users: {user_count_before}")
            print(f"  - Chats: {chat_count_before}")
            print(f"  - Messages: {message_count_before}")

            # Delete test_user2
            response = client.delete(f'/api/admin/users/{test_user2.id}')
            assert response.status_code == 200, f"Failed to delete user: {response.get_json()}"

            # Count after deletion
            user_count_after = User.query.count()
            chat_count_after = Chat.query.count()
            message_count_after = Message.query.count()

            print(f"\n[INFO] After deletion:")
            print(f"  - Users: {user_count_after}")
            print(f"  - Chats: {chat_count_after}")
            print(f"  - Messages: {message_count_after}")

            assert user_count_after == user_count_before - 1, "User not deleted"
            assert chat_count_after == 0, "Chats not cascade deleted"
            assert message_count_after == 0, "Messages not cascade deleted"

            print("\n[PASS] Test 4: Cascade deletion working correctly")

        # Test 5: Prevent self-deletion
        with app.test_client() as client:
            # Login as admin
            client.post('/auth/login',
                json={
                    'username': 'admin',
                    'password': 'Test123!@#'
                },
                follow_redirects=True)

            # Try to delete self
            response = client.delete(f'/api/admin/users/{admin_user.id}')
            assert response.status_code == 400, "Admin should not be able to delete themselves"

            data = response.get_json()
            assert 'Cannot delete your own account' in data['error'], "Wrong error message"

            print("\n[PASS] Test 5: Self-deletion correctly prevented")

        print("\n" + "="*50)
        print("ALL TESTS PASSED!")
        print("="*50)


if __name__ == '__main__':
    test_admin_user_management()
