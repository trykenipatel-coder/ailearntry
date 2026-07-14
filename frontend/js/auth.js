const API_BASE = '';

async function apiRequest(url, method = 'GET', data = null) {
    try {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
        };
        if (data) opts.body = JSON.stringify(data);
        const res = await fetch(url, opts);
        if (!res.ok) {
            console.error(`[API] ${method} ${url} → HTTP ${res.status}`);
            try {
                var errJson = await res.json();
                console.error('[API] Error JSON:', errJson);
                return errJson;
            } catch(e2) {
                var errText = '';
                try { errText = await res.text(); } catch(e) {}
                console.error('[API] Response:', errText.substring(0, 500));
                return { success: false, message: 'Server error (HTTP ' + res.status + ')' };
            }
        }
        const json = await res.json();
        return json;
    } catch (err) {
        console.error(`[API Error] ${url}:`, err);
        return { success: false, message: 'Network error. Check your connection or server.' };
    }
}

function showAlert(message, type = 'info') {
    const existing = document.querySelector('.alert');
    if (existing) existing.remove();
    const div = document.createElement('div');
    div.className = `alert alert-${type}`;
    div.innerHTML = message;
    const target = document.querySelector('.auth-card form') || document.querySelector('.dashboard') || document.body;
    if (target) {
        target.insertBefore(div, target.firstChild);
        setTimeout(() => div.remove(), 4000);
    }
}

function setLoading(btn, loading) {
    if (loading) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;margin:0;display:inline-block"></span> Loading...';
    } else {
        btn.disabled = false;
        btn.textContent = btn.getAttribute('data-original-text') || 'Submit';
    }
}

function initDarkMode() {
    const saved = localStorage.getItem('darkMode');
    const isDark = saved === 'true';
    if (isDark) document.body.classList.add('dark');
    document.querySelectorAll('.dark-toggle').forEach(b => {
        b.innerHTML = isDark ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>' : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    });
}

function toggleDarkMode() {
    const isDark = document.body.classList.toggle('dark');
    localStorage.setItem('darkMode', isDark);
    document.querySelectorAll('.dark-toggle').forEach(b => {
        b.innerHTML = isDark ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>' : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
    });
}

async function checkAuth(redirect = true) {
    const result = await apiRequest('/api/session');
    if (!result.authenticated) {
        if (redirect) window.location.href = '/login';
        return null;
    }
    const nav = document.getElementById('mainNav');
    if (nav) {
        const links = document.getElementById('navLinks');
        if (links) {
            const role = result.role;
            const dashPath = role + '/dashboard';
            let roleLinks = '';
            if (role === 'student') {
                roleLinks = `
                    <li><a href="../student/dashboard.html">Dashboard</a></li>
                    <li><a href="../student/available-quizzes.html">Quizzes</a></li>
                    <li><a href="../student/materials.html">Materials</a></li>
                    <li><a href="../student/results.html">Results</a></li>
                    <li><a href="../student/leaderboard.html">Leaderboard</a></li>
                    <li><a href="../student/exam-coach.html">Exam Coach</a></li>
                `;
            } else if (role === 'mentor') {
                roleLinks = `
                    <li><a href="../mentor/dashboard.html">Dashboard</a></li>
                    <li><a href="../mentor/quizzes.html">Quizzes</a></li>
                    <li><a href="../mentor/create-quiz.html">Create Quiz</a></li>
                    <li><a href="../mentor/ai-quiz.html">AI Quiz</a></li>
                    <li><a href="../mentor/access-codes.html">Codes</a></li>
                    <li><a href="../mentor/materials.html">Materials</a></li>
                    <li><a href="../mentor/analytics.html">Analytics</a></li>
                    <li><a href="../mentor/leaderboard.html">Leaderboard</a></li>
                    <li><a href="../mentor/student-insight.html">Insight Bot</a></li>
                `;
            } else if (role === 'admin') {
                roleLinks = `
                    <li><a href="../admin/dashboard.html">Dashboard</a></li>
                    <li><a href="../admin/manage-students.html">Students</a></li>
                    <li><a href="../admin/manage-mentors.html">Mentors</a></li>
                    <li><a href="../admin/materials.html">Materials</a></li>
                    <li><a href="../admin/quizzes.html">Quizzes</a></li>
                    <li><a href="../admin/student-insight.html">Insight Bot</a></li>
                `;
            }
            links.innerHTML = roleLinks + `<li><button class="dark-toggle" onclick="toggleDarkMode()" title="Toggle dark mode">🌙</button></li>` + `<li><button class="btn-logout" onclick="logout()">Logout</button></li>`;

            // Update logo to always point to dashboard when logged in
            const logo = document.querySelector('.navbar .logo');
            if (logo) {
                const isOnDashboard = window.location.pathname.includes('/' + role + '/');
                if (!isOnDashboard) {
                    logo.href = role + '/dashboard.html';
                } else {
                    logo.href = 'dashboard.html';
                }
            }
        }
    }
    return result;
}

async function logout() {
    await apiRequest('/api/auth/logout', 'POST');
    if (typeof firebaseLogout === 'function') {
        try { await firebaseLogout(); } catch (e) {}
    }
    window.location.href = '/login';
}

function getQueryParam(name) {
    const params = new URLSearchParams(window.location.search);
    return params.get(name);
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
        if (courseField) courseField.style.display = role === 'student' ? 'block' : 'none';
        if (subjectField) subjectField.style.display = role === 'mentor' ? 'block' : 'none';
        if (nameLabel) nameLabel.textContent = role === 'mentor' ? 'Mentor Name' : 'Full Name';
    }
}

// ─── INIT ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Login form (existing SQLite auth)
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = loginForm.querySelector('button[type="submit"]');
            setLoading(btn, true);
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const role = document.getElementById('role').value;

            // Try Firebase auth if available
            if (typeof firebaseEmailSignIn === 'function' && isFirebaseAvailable()) {
                const fbResult = await firebaseEmailSignIn(email, password);
                setLoading(btn, false);
                if (fbResult && fbResult.success) {
                    showAlert(fbResult.message, 'success');
                    setTimeout(() => { window.location.href = `/${fbResult.role}/dashboard`; }, 500);
                    return;
                }
            }

            // Fallback to SQLite auth
            const result = await apiRequest('/api/auth/login', 'POST', { email, password, role });
            setLoading(btn, false);
            if (result.success) {
                    showAlert(result.message, 'success');
                    setTimeout(() => { window.location.href = `/${result.role}/dashboard`; }, 500);
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
            const name = document.getElementById('name').value;
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;

            if (typeof firebaseEmailSignUp === 'function' && isFirebaseAvailable()) {
                const fbResult = await firebaseEmailSignUp(email, password, name, role);
                setLoading(btn, false);
                if (fbResult && fbResult.success) {
                    showAlert(fbResult.message, 'success');
                    setTimeout(() => { window.location.href = `/${fbResult.role}/dashboard`; }, 500);
                    return;
                }
            }

            const data = { name, email, password, role };
            if (role === 'student') data.course = document.getElementById('course')?.value || '';
            if (role === 'mentor') data.subject = document.getElementById('subject')?.value || '';
            const result = await apiRequest('/api/auth/register', 'POST', data);
            setLoading(btn, false);
            if (result.success) {
                showAlert(result.message, 'success');
                if (result.pendingApproval) {
                    setTimeout(() => { window.location.href = '/login'; }, 3000);
                } else {
                    setTimeout(() => { window.location.href = `/${result.role}/dashboard`; }, 500);
                }
            } else {
                showAlert(result.message, 'danger');
            }
        });
    }

    // Google Sign-In button
    const googleBtn = document.getElementById('google-signin-btn');
    if (googleBtn) {
        googleBtn.addEventListener('click', async () => {
            if (typeof firebaseGoogleSignIn === 'function' && isFirebaseAvailable()) {
                googleBtn.disabled = true;
                googleBtn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;margin:0;display:inline-block"></span> Signing in...';
                const result = await firebaseGoogleSignIn();
                googleBtn.disabled = false;
                googleBtn.innerHTML = '<img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" style="width:18px;height:18px"> Sign in with Google';
                if (result && result.success) {
                    showAlert(result.message, 'success');
                    setTimeout(() => { window.location.href = `/${result.role}/dashboard`; }, 500);
                } else if (result) {
                    showAlert(result.message, 'danger');
                }
            } else {
                showAlert('Firebase is not configured. Use email/password login.', 'warning');
            }
        });
    }

    initDarkMode();
    checkAuth(false);
});
