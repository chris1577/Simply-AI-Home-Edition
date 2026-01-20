// Profile Page JavaScript

let currentUser = null;
let twofaStatus = null;

// Initialize theme on page load
function initTheme() {
    // Get saved theme from localStorage (same as main app)
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
}

// Load user profile on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize theme first for consistent appearance
    initTheme();

    await loadUserProfile();
    await load2FAStatus();
    await checkAdminAccess();
});

// Load user profile
async function loadUserProfile() {
    try {
        const response = await fetch('/auth/me');
        if (!response.ok) {
            if (response.status === 401) {
                window.location.href = '/auth/login';
                return;
            }
            throw new Error('Failed to load profile');
        }

        const data = await response.json();
        currentUser = data.user;

        // Update UI
        document.getElementById('profile-username').textContent = currentUser.username;
        document.getElementById('profile-email').textContent = currentUser.email;
        document.getElementById('info-username').textContent = currentUser.username;
        document.getElementById('info-email').textContent = currentUser.email;
        document.getElementById('info-user-id').textContent = currentUser.id;
        document.getElementById('info-created-at').textContent = new Date(currentUser.created_at).toLocaleDateString();
        document.getElementById('info-roles').textContent = currentUser.roles.join(', ') || 'User';

    } catch (error) {
        console.error('Error loading profile:', error);
        showError('Failed to load profile');
    }
}

// Load 2FA status
async function load2FAStatus() {
    try {
        const response = await fetch('/auth/2fa/status');
        if (!response.ok) throw new Error('Failed to load 2FA status');

        const data = await response.json();
        twofaStatus = data;

        if (data.enabled) {
            document.getElementById('twofa-status').innerHTML = '<span class="badge badge-success">Enabled</span>';
            document.getElementById('twofa-disabled-section').style.display = 'none';
            document.getElementById('twofa-enabled-section').style.display = 'block';
            document.getElementById('backup-codes-count-item').style.display = 'flex';
            document.getElementById('backup-codes-count').textContent = data.backup_codes_remaining;
        } else {
            document.getElementById('twofa-status').innerHTML = '<span class="badge badge-warning">Disabled</span>';
            document.getElementById('twofa-disabled-section').style.display = 'block';
            document.getElementById('twofa-enabled-section').style.display = 'none';
            document.getElementById('backup-codes-count-item').style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading 2FA status:', error);
    }
}

// Change password form
document.getElementById('change-password-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;

    const errorDiv = document.getElementById('password-error');
    const successDiv = document.getElementById('password-success');

    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';

    if (newPassword !== confirmPassword) {
        errorDiv.textContent = 'New passwords do not match';
        errorDiv.style.display = 'block';
        return;
    }

    try {
        const response = await fetch('/auth/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        const data = await response.json();

        if (response.ok) {
            successDiv.textContent = 'Password changed successfully!';
            successDiv.style.display = 'block';
            document.getElementById('change-password-form').reset();
        } else {
            if (data.details) {
                errorDiv.innerHTML = '<strong>' + data.error + '</strong><ul>' +
                    data.details.map(err => '<li>' + err + '</li>').join('') +
                    '</ul>';
            } else {
                errorDiv.textContent = data.error || 'Failed to change password';
            }
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = 'Network error. Please try again.';
        errorDiv.style.display = 'block';
    }
});

// Enable 2FA
document.getElementById('enable-2fa-btn').addEventListener('click', async () => {
    try {
        const response = await fetch('/auth/2fa/enroll', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const data = await response.json();
            alert(data.error || 'Failed to start 2FA enrollment');
            return;
        }

        const data = await response.json();

        // Show QR code and enrollment form
        document.getElementById('twofa-qr-code').src = data.qr_code;
        document.getElementById('twofa-secret').textContent = data.secret;
        document.getElementById('twofa-disabled-section').style.display = 'none';
        document.getElementById('twofa-enrollment-section').style.display = 'block';
        document.getElementById('verification-code').focus();

    } catch (error) {
        alert('Network error. Please try again.');
    }
});

// Verify enrollment
document.getElementById('verify-enrollment-btn').addEventListener('click', async () => {
    const code = document.getElementById('verification-code').value;
    const errorDiv = document.getElementById('enrollment-error');

    errorDiv.style.display = 'none';

    if (!code || code.length !== 6) {
        errorDiv.textContent = 'Please enter a valid 6-digit code';
        errorDiv.style.display = 'block';
        return;
    }

    try {
        const response = await fetch('/auth/2fa/verify-enrollment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ code })
        });

        const data = await response.json();

        if (response.ok) {
            // Show backup codes
            displayBackupCodes(data.backup_codes);
            document.getElementById('twofa-enrollment-section').style.display = 'none';
            await load2FAStatus();
        } else {
            errorDiv.textContent = data.error || 'Invalid code. Please try again.';
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = 'Network error. Please try again.';
        errorDiv.style.display = 'block';
    }
});

// Cancel enrollment
document.getElementById('cancel-enrollment-btn').addEventListener('click', () => {
    document.getElementById('twofa-enrollment-section').style.display = 'none';
    document.getElementById('twofa-disabled-section').style.display = 'block';
    document.getElementById('verification-code').value = '';
    document.getElementById('enrollment-error').style.display = 'none';
});

// Disable 2FA
document.getElementById('disable-2fa-btn').addEventListener('click', async () => {
    const password = prompt('Enter your password to disable 2FA:');
    if (!password) return;

    try {
        const response = await fetch('/auth/2fa/disable', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ password })
        });

        const data = await response.json();

        if (response.ok) {
            alert('2FA has been disabled');
            await load2FAStatus();
        } else {
            alert(data.error || 'Failed to disable 2FA');
        }
    } catch (error) {
        alert('Network error. Please try again.');
    }
});

// Regenerate backup codes
document.getElementById('regenerate-codes-btn').addEventListener('click', async () => {
    const code = prompt('Enter a 6-digit code from your authenticator app:');
    if (!code) return;

    try {
        const response = await fetch('/auth/2fa/regenerate-backup-codes', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ code })
        });

        const data = await response.json();

        if (response.ok) {
            displayBackupCodes(data.backup_codes);
            await load2FAStatus();
        } else {
            alert(data.error || 'Failed to regenerate backup codes');
        }
    } catch (error) {
        alert('Network error. Please try again.');
    }
});

// Display backup codes
function displayBackupCodes(codes) {
    const backupCodesList = document.getElementById('backup-codes-list');
    backupCodesList.innerHTML = '';

    codes.forEach(code => {
        const codeDiv = document.createElement('div');
        codeDiv.className = 'backup-code';
        codeDiv.textContent = code;
        backupCodesList.appendChild(codeDiv);
    });

    document.getElementById('backup-codes-section').style.display = 'block';
}

// Close backup codes
document.getElementById('close-backup-codes-btn').addEventListener('click', () => {
    document.getElementById('backup-codes-section').style.display = 'none';
});

// Logout
document.getElementById('logout-btn').addEventListener('click', async () => {
    try {
        const response = await fetch('/auth/logout', {
            method: 'POST'
        });

        if (response.ok) {
            window.location.href = '/auth/login';
        } else {
            alert('Failed to logout');
        }
    } catch (error) {
        alert('Network error. Please try again.');
    }
});

// Back to chat
document.getElementById('back-to-chat-btn').addEventListener('click', () => {
    window.location.href = '/';
});

// Back to chat (top button)
document.getElementById('back-to-chat-btn-top').addEventListener('click', () => {
    window.location.href = '/';
});

// Settings link
document.getElementById('settings-link-btn').addEventListener('click', () => {
    window.location.href = '/auth/settings';
});

// Export all chats
document.getElementById('export-all-chats-btn').addEventListener('click', async () => {
    try {
        // Show loading state
        const btn = document.getElementById('export-all-chats-btn');
        const originalHTML = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exporting...';

        // Create a temporary link and trigger download
        const link = document.createElement('a');
        link.href = '/api/export_all_chats';
        link.download = '';  // Filename is set by the server
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        // Reset button state after a short delay
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = originalHTML;
        }, 2000);

    } catch (error) {
        console.error('Error exporting chats:', error);
        alert('Failed to export chats. Please try again.');

        // Reset button state
        const btn = document.getElementById('export-all-chats-btn');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-download"></i> Export All Chats';
    }
});

function showError(message) {
    alert(message);
}

// Admin User Management Functions
async function checkAdminAccess() {
    // Check if current user has super_admin role
    if (currentUser && currentUser.roles && currentUser.roles.includes('super_admin')) {
        document.getElementById('admin-user-management-section').style.display = 'block';
        await loadAllUsers();
    }
}

async function loadAllUsers() {
    const loadingDiv = document.getElementById('admin-users-loading');
    const errorDiv = document.getElementById('admin-users-error');
    const usersList = document.getElementById('admin-users-list');

    loadingDiv.style.display = 'block';
    errorDiv.style.display = 'none';
    usersList.innerHTML = '';

    try {
        const response = await fetch('/api/admin/users');
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to load users');
        }

        const data = await response.json();
        loadingDiv.style.display = 'none';

        if (data.users.length === 0) {
            usersList.innerHTML = '<p class="users-empty-state">No other users found</p>';
            return;
        }

        // Create table of users
        const table = document.createElement('div');
        table.className = 'users-table-wrapper';

        const tableHTML = `
            <table class="users-table">
                <thead>
                    <tr>
                        <th>Username</th>
                        <th>Age Group</th>
                        <th class="text-center">Chats</th>
                        <th class="text-center">Actions</th>
                    </tr>
                </thead>
                <tbody id="users-table-body">
                </tbody>
            </table>
        `;
        table.innerHTML = tableHTML;
        usersList.appendChild(table);

        const tbody = document.getElementById('users-table-body');

        data.users.forEach(user => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <strong>${escapeHtml(user.username)}</strong>
                    ${!user.is_active ? '<span class="user-inactive-badge">(Inactive)</span>' : ''}
                </td>
                <td>${getAgeGroupBadge(user.age_group)}</td>
                <td class="text-center">${user.chat_count}</td>
                <td class="text-center">
                    <button onclick="deleteUserConfirm(${user.id}, '${escapeHtml(user.username)}')" class="btn-danger" style="padding: 6px 12px; font-size: 12px; width: auto; margin: 0 auto;">
                        <i class="fas fa-trash"></i> Delete
                    </button>
                </td>
            `;
            tbody.appendChild(row);
        });

    } catch (error) {
        loadingDiv.style.display = 'none';
        errorDiv.textContent = error.message || 'Failed to load users';
        errorDiv.style.display = 'block';
    }
}

function getAgeGroupBadge(ageGroup) {
    const badges = {
        'child': '<span class="badge badge-child" title="Under 12 years old"><i class="fas fa-child"></i> Child</span>',
        'teen': '<span class="badge badge-teen" title="12-17 years old"><i class="fas fa-user-graduate"></i> Teen</span>',
        'adult': '<span class="badge badge-adult" title="18+ years old"><i class="fas fa-user"></i> Adult</span>',
        'unknown': '<span class="badge badge-secondary" title="Age not set"><i class="fas fa-question"></i> Unknown</span>'
    };
    return badges[ageGroup] || badges['unknown'];
}

async function deleteUserConfirm(userId, username) {
    const confirmed = confirm(
        `Are you sure you want to delete user "${username}"?\n\n` +
        `This will permanently delete:\n` +
        `- Their account\n` +
        `- All their chat history\n` +
        `- All their uploaded files\n\n` +
        `This action CANNOT be undone!`
    );

    if (!confirmed) return;

    // Second confirmation for extra safety
    const doubleConfirm = confirm(
        `FINAL CONFIRMATION\n\n` +
        `Type YES in the next prompt to confirm deletion of user "${username}"`
    );

    if (!doubleConfirm) return;

    const finalConfirm = prompt(`Type "YES" (in capitals) to confirm deletion of ${username}:`);
    if (finalConfirm !== 'YES') {
        alert('Deletion cancelled - confirmation text did not match');
        return;
    }

    await deleteUser(userId, username);
}

async function deleteUser(userId, username) {
    const errorDiv = document.getElementById('admin-users-error');
    errorDiv.style.display = 'none';

    try {
        const response = await fetch(`/api/admin/users/${userId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (response.ok) {
            alert(`User "${username}" has been deleted successfully.\n\nDeleted ${data.deleted_files} files.`);
            // Reload the users list
            await loadAllUsers();
        } else {
            throw new Error(data.error || 'Failed to delete user');
        }
    } catch (error) {
        errorDiv.textContent = error.message || 'Failed to delete user';
        errorDiv.style.display = 'block';
        alert(`Error: ${error.message}`);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
