const registerForm = document.getElementById('register-form');
const passwordInput = document.getElementById('password');
const dobInput = document.getElementById('date-of-birth');
const errorMessage = document.getElementById('error-message');
const successMessage = document.getElementById('success-message');
const passwordInfoBtn = document.getElementById('password-info-btn');
const passwordRequirementsPopup = document.getElementById('password-requirements');

// Toggle password requirements popup
passwordInfoBtn.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    passwordRequirementsPopup.classList.toggle('show');
});

// Close popup when clicking outside
document.addEventListener('click', (e) => {
    if (!passwordRequirementsPopup.contains(e.target) && e.target !== passwordInfoBtn && !passwordInfoBtn.contains(e.target)) {
        passwordRequirementsPopup.classList.remove('show');
    }
});

// Set date constraints for date of birth input
(function initializeDateInput() {
    if (dobInput) {
        // Set max date to today (can't be born in the future)
        const today = new Date().toISOString().split('T')[0];
        dobInput.setAttribute('max', today);

        // Set min date to 120 years ago
        const minDate = new Date();
        minDate.setFullYear(minDate.getFullYear() - 120);
        dobInput.setAttribute('min', minDate.toISOString().split('T')[0]);
    }
})();

// Password strength indicator
passwordInput.addEventListener('input', () => {
    const password = passwordInput.value;

    // Check each requirement
    const requirements = {
        'req-length': password.length >= 8,
        'req-uppercase': /[A-Z]/.test(password),
        'req-lowercase': /[a-z]/.test(password),
        'req-number': /\d/.test(password)
    };

    for (const [id, met] of Object.entries(requirements)) {
        const element = document.getElementById(id);
        if (met) {
            element.classList.add('requirement-met');
            element.querySelector('i').className = 'fas fa-check-circle';
        } else {
            element.classList.remove('requirement-met');
            element.querySelector('i').className = 'fas fa-circle';
        }
    }
});

registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const email = document.getElementById('email').value;
    const dateOfBirth = document.getElementById('date-of-birth').value;
    const password = document.getElementById('password').value;
    const passwordConfirm = document.getElementById('password-confirm').value;

    errorMessage.style.display = 'none';
    successMessage.style.display = 'none';

    // Client-side validation
    if (!dateOfBirth) {
        errorMessage.textContent = 'Date of birth is required';
        errorMessage.style.display = 'block';
        return;
    }

    // Validate age (must be at least 4 years old)
    const dob = new Date(dateOfBirth);
    const today = new Date();
    let age = today.getFullYear() - dob.getFullYear();
    const monthDiff = today.getMonth() - dob.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
        age--;
    }
    if (age < 4) {
        errorMessage.textContent = 'You must be at least 4 years old to create an account';
        errorMessage.style.display = 'block';
        return;
    }

    if (password !== passwordConfirm) {
        errorMessage.textContent = 'Passwords do not match';
        errorMessage.style.display = 'block';
        return;
    }

    const registerBtn = document.getElementById('register-btn');
    registerBtn.disabled = true;
    registerBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating account...';

    try {
        const response = await fetch('/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, email, password, date_of_birth: dateOfBirth })
        });

        const data = await response.json();

        if (response.ok) {
            successMessage.textContent = 'Account created successfully! Redirecting to login...';
            successMessage.style.display = 'block';
            registerForm.reset();
            setTimeout(() => {
                window.location.href = '/auth/login';
            }, 2000);
        } else if (response.status === 429) {
            errorMessage.textContent = 'Too many registration attempts. Please wait a moment and try again.';
            errorMessage.style.display = 'block';
        } else {
            if (data.details) {
                // Show detailed password errors
                errorMessage.innerHTML = '<strong>' + data.error + '</strong><ul>' +
                    data.details.map(err => '<li>' + err + '</li>').join('') +
                    '</ul>';
            } else {
                errorMessage.textContent = data.error || 'Registration failed';
            }
            errorMessage.style.display = 'block';
        }
    } catch (error) {
        errorMessage.textContent = 'Network error. Please try again.';
        errorMessage.style.display = 'block';
    } finally {
        registerBtn.disabled = false;
        registerBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
    }
});
