const API_BASE = '';

async function apiRequest(url, method = 'GET', data = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (data) opts.body = JSON.stringify(data);

    const res = await fetch(url, opts);
    return res.json();
}

function showAlert(message, type = 'info') {
    const existing = document.querySelector('.alert');
    if (existing) existing.remove();

    const div = document.createElement('div');
    div.className = `alert alert-${type}`;
    div.textContent = message;
    const form = document.querySelector('.auth-card form');
    if (form) {
        form.prepend(div);
        setTimeout(() => div.remove(), 3000);
    }
}

function setLoading(btn, loading) {
    if (loading) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;margin:0"></span> Loading...';
    } else {
        btn.disabled = false;
        btn.textContent = btn.getAttribute('data-original-text') || 'Submit';
    }
}

function switchTab(role) {
    document.querySelectorAll('.role-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.role === role);
    });
    const roleInput = document.getElementById('role');
    if (roleInput) roleInput.value = role;

    const courseField = document.getElementById('course-field');
    const subjectField = document.getElementById('subject-field');
    const nameLabel = document.getElementById('name-label');

    if (document.getElementById('register-form')) {
        if (role === 'student') {
            if (courseField) courseField.style.display = 'block';
            if (subjectField) subjectField.style.display = 'none';
            if (nameLabel) nameLabel.textContent = 'Full Name';
        } else if (role === 'mentor') {
            if (courseField) courseField.style.display = 'none';
            if (subjectField) subjectField.style.display = 'block';
            if (nameLabel) nameLabel.textContent = 'Mentor Name';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Login form
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = loginForm.querySelector('button[type="submit"]');
            setLoading(btn, true);

            const data = {
                email: document.getElementById('email').value,
                password: document.getElementById('password').value,
                role: document.getElementById('role').value,
            };

            const result = await apiRequest('/api/auth/login', 'POST', data);
            setLoading(btn, false);

            if (result.success) {
                showAlert(result.message, 'success');
                setTimeout(() => {
                    window.location.href = `/${result.role}/dashboard`;
                }, 500);
            } else {
                showAlert(result.message, 'danger');
            }
        });
    }

    // Register form
    const registerForm = document.getElementById('register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = registerForm.querySelector('button[type="submit"]');
            setLoading(btn, true);

            const role = document.getElementById('role').value;
            const data = {
                name: document.getElementById('name').value,
                email: document.getElementById('email').value,
                password: document.getElementById('password').value,
                role: role,
            };

            if (role === 'student') {
                data.course = document.getElementById('course')?.value || '';
            } else if (role === 'mentor') {
                data.subject = document.getElementById('subject')?.value || '';
            }

            const result = await apiRequest('/api/auth/register', 'POST', data);
            setLoading(btn, false);

            if (result.success) {
                showAlert(result.message, 'success');
                setTimeout(() => {
                    window.location.href = `/${role}/dashboard`;
                }, 500);
            } else {
                showAlert(result.message, 'danger');
            }
        });
    }

    // Logout
    document.querySelectorAll('.btn-logout').forEach(btn => {
        btn.addEventListener('click', async () => {
            await apiRequest('/api/auth/logout', 'POST');
            window.location.href = '/login';
        });
    });
});
