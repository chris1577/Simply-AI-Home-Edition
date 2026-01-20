"""
Quick Test Script for Phase 2 Authentication

This script performs basic smoke tests to verify the authentication system is working.
"""

import requests
import sys

BASE_URL = "http://localhost:5000"

def test_health():
    """Test if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Server is running")
            return True
        else:
            print("✗ Server returned status", response.status_code)
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Server is not running. Start it with: python run.py")
        return False
    except Exception as e:
        print(f"✗ Error connecting to server: {e}")
        return False

def test_registration():
    """Test user registration"""
    try:
        data = {
            "username": "testuser123",
            "email": "testuser123@example.com",
            "password": "TestPassword123!"
        }
        response = requests.post(f"{BASE_URL}/auth/register", json=data, timeout=5)

        if response.status_code == 201:
            print("✓ User registration works")
            return True
        elif response.status_code == 400 and "already exists" in response.text:
            print("✓ User registration works (user already exists)")
            return True
        else:
            print(f"✗ Registration failed: {response.json()}")
            return False
    except Exception as e:
        print(f"✗ Error testing registration: {e}")
        return False

def test_login():
    """Test user login"""
    try:
        data = {
            "username": "testuser123",
            "password": "TestPassword123!"
        }
        response = requests.post(f"{BASE_URL}/auth/login", json=data, timeout=5)

        if response.status_code == 200:
            result = response.json()
            if 'requires_2fa' in result and result['requires_2fa']:
                print("✓ User login works (2FA required)")
            else:
                print("✓ User login works")
            return True
        else:
            print(f"✗ Login failed: {response.json()}")
            return False
    except Exception as e:
        print(f"✗ Error testing login: {e}")
        return False

def test_jwt_login():
    """Test JWT token login"""
    try:
        data = {
            "username": "testuser123",
            "password": "TestPassword123!"
        }
        response = requests.post(f"{BASE_URL}/auth/token/login", json=data, timeout=5)

        if response.status_code == 200:
            result = response.json()
            if 'access_token' in result and 'refresh_token' in result:
                print("✓ JWT authentication works")
                return True

        print(f"✗ JWT login failed: {response.json()}")
        return False
    except Exception as e:
        print(f"✗ Error testing JWT login: {e}")
        return False

def main():
    print("=" * 60)
    print("  Phase 2 Authentication - Quick Test")
    print("=" * 60)
    print()

    tests_passed = 0
    tests_total = 4

    # Test 1: Server health
    if test_health():
        tests_passed += 1
    else:
        print("\nPlease start the server first: python run.py")
        sys.exit(1)

    print()

    # Test 2: Registration
    if test_registration():
        tests_passed += 1

    # Test 3: Login
    if test_login():
        tests_passed += 1

    # Test 4: JWT
    if test_jwt_login():
        tests_passed += 1

    print()
    print("=" * 60)
    print(f"  Results: {tests_passed}/{tests_total} tests passed")
    print("=" * 60)
    print()

    if tests_passed == tests_total:
        print("✓ All basic tests passed!")
        print("\nNext steps:")
        print("  1. Open browser: http://localhost:5000/auth/login")
        print("  2. Test 2FA enrollment at: http://localhost:5000/auth/profile")
        print("  3. See TESTING_GUIDE.md for comprehensive tests")
    else:
        print("✗ Some tests failed. Check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
