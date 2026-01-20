const loginForm = document.getElementById('login-form');
const twofaForm = document.getElementById('twofa-form');
const errorMessage = document.getElementById('error-message');
const successMessage = document.getElementById('success-message');
const twofaErrorMessage = document.getElementById('twofa-error-message');

let twofa_token = null;

// Standard login
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    errorMessage.style.display = 'none';
    successMessage.style.display = 'none';

    const loginBtn = document.getElementById('login-btn');
    loginBtn.disabled = true;
    loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';

    try {
        const response = await fetch('/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            if (data.requires_2fa) {
                // Show 2FA form
                twofa_token = data['2fa_token'];
                loginForm.style.display = 'none';
                twofaForm.style.display = 'block';
                document.getElementById('twofa-code').focus();
            } else {
                // Login successful
                successMessage.textContent = 'Login successful! Redirecting...';
                successMessage.style.display = 'block';
                setTimeout(() => {
                    window.location.href = '/';
                }, 1000);
            }
        } else if (response.status === 429) {
            errorMessage.textContent = 'Too many login attempts. Please wait a moment and try again.';
            errorMessage.style.display = 'block';
        } else {
            errorMessage.textContent = data.error || 'Login failed';
            errorMessage.style.display = 'block';
        }
    } catch (error) {
        errorMessage.textContent = 'Network error. Please try again.';
        errorMessage.style.display = 'block';
    } finally {
        loginBtn.disabled = false;
        loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Sign In';
    }
});

// 2FA verification
twofaForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const code = document.getElementById('twofa-code').value;
    const useBackup = document.getElementById('use-backup-code').checked;

    twofaErrorMessage.style.display = 'none';

    const verifyBtn = document.getElementById('verify-2fa-btn');
    verifyBtn.disabled = true;
    verifyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Verifying...';

    try {
        const response = await fetch('/auth/verify-2fa', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                '2fa_token': twofa_token,
                code: code,
                use_backup_code: useBackup
            })
        });

        const data = await response.json();

        if (response.ok) {
            successMessage.textContent = 'Login successful! Redirecting...';
            successMessage.style.display = 'block';
            twofaForm.style.display = 'none';
            setTimeout(() => {
                window.location.href = '/';
            }, 1000);
        } else if (response.status === 429) {
            twofaErrorMessage.textContent = 'Too many verification attempts. Please wait a moment and try again.';
            twofaErrorMessage.style.display = 'block';
            document.getElementById('twofa-code').value = '';
        } else {
            twofaErrorMessage.textContent = data.error || 'Verification failed';
            twofaErrorMessage.style.display = 'block';
            document.getElementById('twofa-code').value = '';
            document.getElementById('twofa-code').focus();
        }
    } catch (error) {
        twofaErrorMessage.textContent = 'Network error. Please try again.';
        twofaErrorMessage.style.display = 'block';
    } finally {
        verifyBtn.disabled = false;
        verifyBtn.innerHTML = '<i class="fas fa-check-circle"></i> Verify & Login';
    }
});

// Back to login
document.getElementById('back-to-login-btn').addEventListener('click', () => {
    twofaForm.style.display = 'none';
    loginForm.style.display = 'block';
    twofaErrorMessage.style.display = 'none';
    document.getElementById('twofa-code').value = '';
    twofa_token = null;
});

// Handle backup code toggle
document.getElementById('use-backup-code').addEventListener('change', (e) => {
    const codeInput = document.getElementById('twofa-code');
    if (e.target.checked) {
        codeInput.placeholder = 'XXXX-XXXX';
        codeInput.maxLength = 9;
        codeInput.pattern = '[0-9A-F]{4}-[0-9A-F]{4}';
    } else {
        codeInput.placeholder = '000000';
        codeInput.maxLength = 6;
        codeInput.pattern = '[0-9]{6}';
    }
    codeInput.value = '';
});
