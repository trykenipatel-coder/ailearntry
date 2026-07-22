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
            const cp = window.location.pathname.split('/').pop().replace('.html','');
            const A = (href) => href.split('/').pop().replace('.html','') === cp ? ' active' : '';

            let roleLinks = '';
            const I = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">${d}</svg>`;
            if (role === 'student') {
                const h = (p) => window.location.pathname.includes(p) ? ' active' : '';
                roleLinks = `
                    <li class="nav-dropdown">
                        <button class="nav-drop-btn${h('dashboard') || h('passport') || h('semester')}">Overview<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg></button>
                        <div class="nav-drop-menu">
                            <a href="../student/dashboard.html" class="nav-drop-item${h('dashboard')}">${I('<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>')}Dashboard</a>
                            <a href="../student/learning-passport.html" class="nav-drop-item${h('passport')}">${I('<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>')}Learning Passport</a>
                            <a href="../student/semester-report.html" class="nav-drop-item${h('semester')}">${I('<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>')}Semester Report</a>
                        </div>
                    </li>
                    <li class="nav-dropdown">
                        <button class="nav-drop-btn${h('quiz') || h('material') || h('result')}">Learning<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg></button>
                        <div class="nav-drop-menu">
                            <a href="../student/available-quizzes.html" class="nav-drop-item${h('available')}">${I('<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>')}Available Quizzes</a>
                            <a href="../student/materials.html" class="nav-drop-item${h('material')}">${I('<path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>')}Study Materials</a>
                            <a href="../student/results.html" class="nav-drop-item${h('result')}">${I('<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>')}My Results</a>
                        </div>
                    </li>
                    <li class="nav-dropdown">
                        <button class="nav-drop-btn${h('analytics') || h('revision') || h('recommendation') || h('leader')}">Progress<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg></button>
                        <div class="nav-drop-menu">
                            <a href="../student/adaptive-analytics.html" class="nav-drop-item${h('analytics')}">${I('<path d="M18 20V10M12 20V4M6 20v-6"/>')}Analytics</a>
                            <a href="../student/revision-schedule.html" class="nav-drop-item${h('revision')}">${I('<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>')}Revision Schedule</a>
                            <a href="../student/recommendations.html" class="nav-drop-item${h('recommendation')}">${I('<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>')}Recommendations</a>
                            <a href="../student/leaderboard.html" class="nav-drop-item${h('leader')}">${I('<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>')}Leaderboard</a>
                        </div>
                    </li>
                    <li class="nav-dropdown">
                        <button class="nav-drop-btn${h('coach') || h('resources') || h('id-verify')}">AI Tools<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg></button>
                        <div class="nav-drop-menu">
                            <a href="../student/exam-coach.html" class="nav-drop-item${h('coach')}">${I('<path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/>')}Exam Coach</a>
                            <a href="../student/id-verification.html" class="nav-drop-item${h('id-verify')}">${I('<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>')}ID Verification</a>
                            <a href="../student/resources.html" class="nav-drop-item${h('resources')}">${I('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>')}Resource Explorer</a>
                        </div>
                    </li>`;
            } else if (role === 'mentor') {
                const h = (p) => window.location.pathname.includes(p) ? ' active' : '';
                roleLinks = `
                    <li class="nav-dropdown">
                        <button class="nav-drop-btn${h('dashboard') || h('leader') || h('analytics-dash')}">Overview<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg></button>
                        <div class="nav-drop-menu">
                            <a href="../mentor/dashboard.html" class="nav-drop-item${h('dashboard')}">${I('<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>')}Dashboard</a>
                            <a href="../mentor/analytics-dashboard.html" class="nav-drop-item${h('analytics-dash')}">${I('<path d="M18 20V10M12 20V4M6 20v-6"/>')}Analytics Dashboard</a>
                            <a href="../mentor/leaderboard.html" class="nav-drop-item${h('leader')}">${I('<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>')}Leaderboard</a>
                        </div>
                    </li>
                    <li class="nav-dropdown">
                        <button class="nav-drop-btn${h('quiz') || h('create') || h('ai-quiz') || h('access')}">Quizzes<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg></button>
                        <div class="nav-drop-menu">
                            <a href="../mentor/quizzes.html" class="nav-drop-item${h('quizzes')}">${I('<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>')}All Quizzes</a>
                            <a href="../mentor/create-quiz.html" class="nav-drop-item${h('create')}">${I('<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>')}Create Quiz</a>
                            <a href="../mentor/ai-quiz.html" class="nav-drop-item${h('ai-quiz')}">${I('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>')}AI Quiz Generator</a>
                            <a href="../mentor/access-codes.html" class="nav-drop-item${h('access')}">${I('<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>')}Access Codes</a>
                        </div>
                    </li>
                    <li class="nav-dropdown">
                        <button class="nav-drop-btn${h('material') || h('analytics') || h('insight') || h('intervention') || h('resources') || h('proctor')}">Tools<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg></button>
                        <div class="nav-drop-menu">
                            <a href="../mentor/materials.html" class="nav-drop-item${h('material')}">${I('<path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>')}Study Materials</a>
                            <a href="../mentor/analytics.html" class="nav-drop-item${h('analytics')}">${I('<path d="M18 20V10M12 20V4M6 20v-6"/>')}Analytics</a>
                            <a href="../mentor/interventions.html" class="nav-drop-item${h('intervention')}">${I('<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>')}Interventions</a>
                            <a href="../mentor/proctoring.html" class="nav-drop-item${h('proctor')}">${I('<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>')}Proctoring</a>
                            <a href="../mentor/student-insight.html" class="nav-drop-item${h('insight')}">${I('<path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/>')}Student Insight Bot</a>
                            <a href="../mentor/resources.html" class="nav-drop-item${h('resources')}">${I('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>')}Resource Explorer</a>
                        </div>
                    </li>`;
            } else if (role === 'admin') {
                const h = (p) => window.location.pathname.includes(p) ? ' active' : '';
                roleLinks = `
                    <li class="nav-dropdown">
                        <button class="nav-drop-btn${h('dashboard')}">Overview<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg></button>
                        <div class="nav-drop-menu">
                            <a href="../admin/dashboard.html" class="nav-drop-item${h('dashboard')}">${I('<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>')}Dashboard</a>
                        </div>
                    </li>
                    <li class="nav-dropdown">
                        <button class="nav-drop-btn${h('student') || h('mentor') || h('material') || h('quiz') || h('insight')}">Management<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><polyline points="6 9 12 15 18 9"/></svg></button>
                        <div class="nav-drop-menu">
                            <a href="../admin/manage-students.html" class="nav-drop-item${h('student')}">${I('<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>')}Manage Students</a>
                            <a href="../admin/manage-mentors.html" class="nav-drop-item${h('mentor')}">${I('<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>')}Manage Mentors</a>
                            <a href="../admin/materials.html" class="nav-drop-item${h('material')}">${I('<path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>')}Study Materials</a>
                            <a href="../admin/quizzes.html" class="nav-drop-item${h('quiz')}">${I('<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>')}All Quizzes</a>
                            <a href="../admin/student-insight.html" class="nav-drop-item${h('insight')}">${I('<path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/>')}Student Insight Bot</a>
                        </div>
                    </li>`;
            }
            links.innerHTML = roleLinks + `<li><button class="dark-toggle" onclick="toggleDarkMode()" title="Toggle dark mode"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg></button></li>` + `<li><button class="btn-logout" onclick="logout()">Logout</button></li>`;

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
