function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

async function loadAdminDashboard() {
    const auth = await checkAuth();
    if (!auth || auth.role !== 'admin') { window.location.href = '../login.html'; return; }

    const result = await apiRequest('/api/admin/dashboard');
    if (!result.success) return;

    const d = result.data;
    setText('total-students', d.total_students);
    setText('total-mentors', d.total_mentors);
    setText('total-quizzes', d.total_quizzes);
    setText('total-attempts', d.total_attempts);
    setText('total-materials', d.total_materials || 0);
    setText('avg-accuracy', (d.avg_accuracy || 0) + '%');

    const recentStudents = document.getElementById('recent-students');
    if (recentStudents && d.recent_students.length) {
        recentStudents.innerHTML = d.recent_students.map(s => `
            <tr><td><code>${s.student_code || ''}</code></td><td>${s.name}</td><td>${s.email}</td><td>${s.course || 'N/A'}</td><td>${s.registration_date}</td></tr>
        `).join('');
    }

    const recentMentors = document.getElementById('recent-mentors');
    if (recentMentors && d.recent_mentors.length) {
        recentMentors.innerHTML = d.recent_mentors.map(m => `
            <tr><td>${m.mentor_name}</td><td>${m.email}</td><td>${m.subject || 'N/A'}</td></tr>
        `).join('');
    }

    loadAdminAnalytics();
    loadSystemStatus();
    loadAnnouncements();
}

async function loadSystemStatus() {
    const result = await apiRequest('/api/system/status');
    if (!result.success) return;
    const container = document.getElementById('system-status');
    if (!container) return;
    container.innerHTML = `
        <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:16px">
            <span class="badge ${result.server === 'running' ? 'badge-success' : 'badge-danger'}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px;height:12px;vertical-align:middle;margin-right:3px"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>Server: ${result.server}</span>
            <span class="badge badge-info"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px;height:12px;vertical-align:middle;margin-right:3px"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>DB: ${result.database}</span>
            <span class="badge ${result.gemini ? 'badge-success' : 'badge-danger'}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px;height:12px;vertical-align:middle;margin-right:3px"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>AI Engine: ${result.gemini ? 'Connected' : 'Not Connected'}</span>
            <span class="badge ${result.firebase ? 'badge-success' : 'badge-danger'}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px;height:12px;vertical-align:middle;margin-right:3px"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>Firebase: ${result.firebase ? 'Connected' : 'Not Connected'}</span>
        </div>`;
}

async function loadStudents() {
    const result = await apiRequest('/api/admin/manage-students');
    if (!result.success) return;
    const tbody = document.querySelector('#students-table tbody');
    if (!tbody) return;
    if (!result.data.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center">No students registered.</td></tr>';
        return;
    }
    tbody.innerHTML = result.data.map(s => `
        <tr>
            <td><code>${s.student_code || ''}</code></td>
            <td>${s.name}</td>
            <td>${s.email}</td>
            <td>${s.course || 'N/A'}</td>
            <td>${s.quiz_count || 0}</td>
            <td>${s.avg_accuracy || 0}%</td>
            <td><div style="display:flex;gap:4px">
                <button class="btn btn-ghost btn-sm" onclick="viewStudentProfile(${s.student_id})" title="View Profile"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>
                <button class="btn btn-ghost btn-sm" onclick="editStudent(${s.student_id})" title="Edit"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
                <button class="btn btn-danger btn-sm" onclick="deleteStudent(${s.student_id})" title="Delete"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
            </div></td>
        </tr>
    `).join('');
}

function escHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ─── STUDENT PROFILE MODAL ──────────────────────────────────────────
async function viewStudentProfile(studentId) {
    const result = await apiRequest('/api/admin/student/' + studentId);
    if (!result.success) { showAlert(result.message, 'danger'); return; }
    const s = result.data;
    const html = '<div class="modal-overlay" id="profile-modal" style="display:flex">' +
        '<div class="modal-box" style="max-width:480px">' +
            '<button class="modal-close" onclick="document.getElementById(\'profile-modal\').remove()">&times;</button>' +
            '<h2 style="margin-bottom:20px">Student Profile</h2>' +
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">' +
                '<div><div style="font-size:0.7rem;color:var(--neutral-400);text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px">Student Code</div><div style="font-weight:600">' + escHtml(s.student_code || '-') + '</div></div>' +
                '<div><div style="font-size:0.7rem;color:var(--neutral-400);text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px">Name</div><div style="font-weight:600">' + escHtml(s.name) + '</div></div>' +
                '<div><div style="font-size:0.7rem;color:var(--neutral-400);text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px">Email</div><div style="font-weight:600">' + escHtml(s.email) + '</div></div>' +
                '<div><div style="font-size:0.7rem;color:var(--neutral-400);text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px">Course</div><div style="font-weight:600">' + escHtml(s.course || 'N/A') + '</div></div>' +
                '<div><div style="font-size:0.7rem;color:var(--neutral-400);text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px">Registered</div><div style="font-weight:600">' + escHtml(s.registration_date ? s.registration_date.slice(0,10) : '-') + '</div></div>' +
            '</div>' +
            '<div style="display:flex;gap:12px;justify-content:flex-end;margin-top:24px">' +
                '<button class="btn btn-secondary" onclick="document.getElementById(\'profile-modal\').remove()">Close</button>' +
            '</div>' +
        '</div>' +
    '</div>';
    document.body.insertAdjacentHTML('beforeend', html);
}

// ─── STUDENT EDIT MODAL ─────────────────────────────────────────────
async function editStudent(studentId) {
    const result = await apiRequest('/api/admin/student/' + studentId);
    if (!result.success) { showAlert(result.message, 'danger'); return; }
    const s = result.data;
    const html = '<div class="modal-overlay" id="edit-student-modal" style="display:flex">' +
        '<div class="modal-box" style="max-width:480px">' +
            '<button class="modal-close" onclick="document.getElementById(\'edit-student-modal\').remove()">&times;</button>' +
            '<h2 style="margin-bottom:20px">Edit Student</h2>' +
            '<div id="edit-student-feedback" style="margin-bottom:12px"></div>' +
            '<input type="hidden" id="edit-student-id" value="' + s.student_id + '">' +
            '<div class="form-group"><label>Name</label><input type="text" id="edit-student-name" value="' + escHtml(s.name) + '" style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:0.8125rem"></div>' +
            '<div class="form-group"><label>Email</label><input type="email" id="edit-student-email" value="' + escHtml(s.email) + '" style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:0.8125rem"></div>' +
            '<div class="form-group"><label>Course</label><input type="text" id="edit-student-course" value="' + escHtml(s.course || '') + '" style="width:100%;padding:9px 12px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:0.8125rem"></div>' +
            '<div style="display:flex;gap:12px;justify-content:flex-end;margin-top:24px">' +
                '<button class="btn btn-secondary" onclick="document.getElementById(\'edit-student-modal\').remove()">Cancel</button>' +
                '<button class="btn btn-primary" onclick="saveStudentEdit()">Save Changes</button>' +
            '</div>' +
        '</div>' +
    '</div>';
    document.body.insertAdjacentHTML('beforeend', html);
}

async function saveStudentEdit() {
    const id = document.getElementById('edit-student-id').value;
    const name = document.getElementById('edit-student-name').value.trim();
    const email = document.getElementById('edit-student-email').value.trim();
    const course = document.getElementById('edit-student-course').value.trim();
    if (!name || !email) { document.getElementById('edit-student-feedback').innerHTML = '<div class="alert alert-danger">Name and email are required.</div>'; return; }
    const result = await apiRequest('/api/admin/student/' + id, 'PUT', { name, email, course });
    if (result.success) {
        document.getElementById('edit-student-modal').remove();
        showAlert('Student updated successfully!', 'success');
        loadStudents();
    } else {
        document.getElementById('edit-student-feedback').innerHTML = '<div class="alert alert-danger">' + escHtml(result.message) + '</div>';
    }
}

let allMentorsData = [];

async function loadMentors() {
    const result = await apiRequest('/api/admin/manage-mentors');
    if (!result.success) return;
    allMentorsData = result.data;
    renderMentors(allMentorsData);
}

function renderMentors(data) {
    const tbody = document.querySelector('#mentors-table tbody');
    if (!tbody) return;
    const countEl = document.getElementById('mentor-count');
    if (countEl) countEl.textContent = data.length;
    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--neutral-400)">No mentors found.</td></tr>';
        return;
    }
    tbody.innerHTML = data.map((m, i) => {
        const status = m.status || 'active';
        const statusColors = {
            pending: { bg: '#fef3c7', text: '#92400e', border: '#fde68a' },
            active: { bg: '#d1fae5', text: '#065f46', border: '#a7f3d0' },
            rejected: { bg: '#fee2e2', text: '#991b1b', border: '#fecaca' },
            suspended: { bg: '#e5e7eb', text: '#374151', border: '#d1d5db' },
        };
        const sc = statusColors[status] || statusColors.active;
        const statusBadge = `<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 10px;border-radius:12px;font-size:0.7rem;font-weight:600;background:${sc.bg};color:${sc.text};border:1px solid ${sc.border}">${status.charAt(0).toUpperCase() + status.slice(1)}</span>`;

        let actions = '';
        if (status === 'pending') {
            actions = `
                <button class="btn btn-sm" style="background:#d1fae5;color:#065f46;border:1px solid #a7f3d0;cursor:pointer" onclick="approveMentor(${m.mentor_id})">Approve</button>
                <button class="btn btn-sm" style="background:#fee2e2;color:#991b1b;border:1px solid #fecaca;cursor:pointer" onclick="rejectMentor(${m.mentor_id})">Reject</button>`;
        } else if (status === 'active') {
            actions = `
                <button class="btn btn-ghost btn-sm" onclick="viewMentorAnalytics(${m.mentor_id})" title="Analytics"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg></button>
                <button class="btn btn-sm" style="background:#e5e7eb;color:#374151;border:1px solid #d1d5db;cursor:pointer" onclick="suspendMentor(${m.mentor_id})" title="Suspend">Suspend</button>`;
        } else if (status === 'suspended' || status === 'rejected') {
            actions = `
                <button class="btn btn-sm" style="background:#d1fae5;color:#065f46;border:1px solid #a7f3d0;cursor:pointer" onclick="reactivateMentor(${m.mentor_id})">Reactivate</button>`;
        }

        return `
        <tr>
            <td style="font-weight:600;color:var(--neutral-400)">${i + 1}</td>
            <td><strong>${m.mentor_name || m.name || ''}</strong></td>
            <td>${m.email}</td>
            <td>${m.subject || 'N/A'}</td>
            <td>${statusBadge}</td>
            <td><span class="badge badge-primary">${m.quiz_count || 0}</span></td>
            <td><div style="display:flex;gap:4px;flex-wrap:wrap">${actions}</div></td>
        </tr>`;
    }).join('');
}

function filterMentors() {
    const q = document.getElementById('search-input')?.value?.toLowerCase() || '';
    const sf = document.getElementById('status-filter')?.value || 'all';
    const filtered = allMentorsData.filter(m => {
        const matchQ = (m.mentor_name || '').toLowerCase().includes(q) ||
            (m.email || '').toLowerCase().includes(q) ||
            (m.subject || '').toLowerCase().includes(q);
        const matchStatus = sf === 'all' || (m.status || 'active') === sf;
        return matchQ && matchStatus;
    });
    renderMentors(filtered);
}

async function approveMentor(id) {
    if (!confirm('Approve this mentor?')) return;
    const result = await apiRequest(`/api/admin/approve-mentor/${id}`, 'POST');
    if (result.success) { showAlert(result.message, 'success'); loadMentors(); }
}

async function rejectMentor(id) {
    if (!confirm('Reject this mentor?')) return;
    const result = await apiRequest(`/api/admin/reject-mentor/${id}`, 'POST');
    if (result.success) { showAlert(result.message, 'success'); loadMentors(); }
}

async function suspendMentor(id) {
    if (!confirm('Suspend this mentor? They will no longer be able to log in.')) return;
    const result = await apiRequest(`/api/admin/suspend-mentor/${id}`, 'POST');
    if (result.success) { showAlert(result.message, 'success'); loadMentors(); }
}

async function reactivateMentor(id) {
    if (!confirm('Reactivate this mentor?')) return;
    const result = await apiRequest(`/api/admin/reactivate-mentor/${id}`, 'POST');
    if (result.success) { showAlert(result.message, 'success'); loadMentors(); }
}

async function deleteStudent(id) {
    if (!confirm('Are you sure you want to delete this student?')) return;
    const result = await apiRequest(`/api/admin/delete-student/${id}`, 'DELETE');
    if (result.success) { showAlert(result.message, 'success'); loadStudents(); }
}

async function deleteMentor(id) {
    if (!confirm('Delete this mentor and all their quizzes?')) return;
    const result = await apiRequest(`/api/admin/delete-mentor/${id}`, 'DELETE');
    if (result.success) { showAlert(result.message, 'success'); loadMentors(); }
}

async function editMentor(id) {
    const result = await apiRequest(`/api/admin/mentor/${id}`);
    if (!result.success) { showAlert(result.message, 'danger'); return; }
    const m = result.data;
    document.getElementById('edit-mentor-id').value = id;
    document.getElementById('edit-mentor-name').value = m.mentor_name || '';
    document.getElementById('edit-mentor-email').value = m.email || '';
    document.getElementById('edit-mentor-subject').value = m.subject || '';
    document.getElementById('edit-mentor-modal').classList.remove('hidden');
}

function closeEditMentor() {
    document.getElementById('edit-mentor-modal').classList.add('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('edit-mentor-form');
    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('edit-mentor-id').value;
            const result = await apiRequest(`/api/admin/mentor/${id}`, 'PUT', {
                name: document.getElementById('edit-mentor-name').value,
                email: document.getElementById('edit-mentor-email').value,
                subject: document.getElementById('edit-mentor-subject').value,
            });
            if (result.success) {
                showAlert(result.message, 'success');
                closeEditMentor();
                loadMentors();
            } else {
                showAlert(result.message, 'danger');
            }
        });
    }
});

async function viewMentorAnalytics(id) {
    document.getElementById('analytics-modal-title').textContent = 'Mentor Analytics';
    document.getElementById('analytics-modal-body').innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    document.getElementById('mentor-analytics-modal').classList.remove('hidden');

    const result = await apiRequest(`/api/admin/mentor-analytics/${id}`);
    if (!result.success) {
        document.getElementById('analytics-modal-body').innerHTML = `<div class="alert alert-danger">${result.message}</div>`;
        return;
    }
    const d = result.data;
    const m = d.mentor;
    const dist = d.difficulty_distribution || [];
    const res = d.results || {};
    const total = res.total_attempts || 0;
    const acc = res.avg_accuracy || 0;

    document.getElementById('analytics-modal-title').textContent = `Analytics: ${m.mentor_name}`;
    document.getElementById('analytics-modal-body').innerHTML = `
        <div class="stats-grid" style="margin-bottom:16px;grid-template-columns:repeat(2,1fr)">
            <div class="stat-card" style="padding:14px 18px">
                <div class="label">Quizzes</div>
                <div class="value" style="font-size:1.25rem">${d.quiz_count}</div>
            </div>
            <div class="stat-card" style="padding:14px 18px">
                <div class="label">Questions</div>
                <div class="value" style="font-size:1.25rem">${d.total_questions}</div>
            </div>
            <div class="stat-card" style="padding:14px 18px">
                <div class="label">Student Attempts</div>
                <div class="value" style="font-size:1.25rem">${total}</div>
            </div>
            <div class="stat-card" style="padding:14px 18px">
                <div class="label">Avg Accuracy</div>
                <div class="value" style="font-size:1.25rem">${acc}%</div>
            </div>
        </div>
        ${dist.length ? `
            <h4 style="margin-bottom:8px;font-size:0.8125rem">Difficulty Distribution</h4>
            <div style="display:flex;gap:8px;margin-bottom:16px">
                ${dist.map(dd => `
                    <span class="badge ${dd.difficulty === 'Easy' ? 'badge-success' : dd.difficulty === 'Medium' ? 'badge-warning' : 'badge-danger'}" style="font-size:0.75rem;padding:4px 12px">
                        ${dd.difficulty}: ${dd.count}
                    </span>
                `).join('')}
            </div>
        ` : ''}
        <div style="display:flex;gap:8px;padding:12px 16px;background:var(--neutral-50);border-radius:var(--radius-sm);font-size:0.8125rem;color:var(--neutral-500)">
            <span><svg viewBox="0 0 24 24" fill="none" stroke="var(--green-500)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:3px"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>Pass: ${res.passes || 0}</span>
            <span><svg viewBox="0 0 24 24" fill="none" stroke="var(--red-500)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:3px"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>Fail: ${res.fails || 0}</span>
            <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:2px"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>Pass Rate: ${total ? ((res.passes||0)/total*100).toFixed(1) : 0}%</span>
        </div>
        <div style="margin-top:16px;text-align:right">
            <button class="btn btn-secondary btn-sm" onclick="closeMentorAnalytics()">Close</button>
        </div>
    `;
}

function closeMentorAnalytics() {
    document.getElementById('mentor-analytics-modal').classList.add('hidden');
}

async function loadMentorAnalyticsSummary() {
    const result = await apiRequest('/api/admin/mentor-analytics');
    if (!result.success) return;
    const d = result.data;
    const container = document.getElementById('mentor-analytics-area');
    if (!container) return;

    let weeklyHtml = '';
    if (d.weekly_activity && d.weekly_activity.length) {
        const max = Math.max(...d.weekly_activity.map(w => w.count), 1);
        weeklyHtml = d.weekly_activity.map(w => {
            const h = Math.max((w.count / max) * 110, 8);
            const dayLabel = new Date(w.day + 'T00:00:00').toLocaleDateString('en', {weekday:'short'});
            return `<div style="flex:1;text-align:center;display:flex;flex-direction:column;justify-content:end;height:130px">
                <div style="background:linear-gradient(180deg,var(--brand-400),var(--brand-600));border-radius:4px 4px 0 0;height:${h}px;margin:0 auto;width:100%;max-width:32px;transition:height 0.3s ease"></div>
                <div style="font-size:0.65rem;color:var(--neutral-400);margin-top:6px;font-weight:500">${dayLabel}</div>
                <div style="font-size:0.7rem;color:var(--neutral-500);font-weight:700">${w.count}</div>
            </div>`;
        }).join('');
    }

    container.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <div class="card" style="padding:20px">
                <div class="card-header" style="margin-bottom:12px;padding-bottom:10px;font-size:0.875rem">Mentor Analytics Summary</div>
                <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;text-align:center">
                    <div>
                        <div style="font-size:1.25rem;font-weight:700;color:var(--neutral-900)">${d.total_mentors}</div>
                        <div style="font-size:0.65rem;color:var(--neutral-400)">Total</div>
                    </div>
                    <div>
                        <div style="font-size:1.25rem;font-weight:700;color:var(--neutral-900)">${d.mentors_with_quizzes}</div>
                        <div style="font-size:0.65rem;color:var(--neutral-400)">Active</div>
                    </div>
                    <div>
                        <div style="font-size:1.25rem;font-weight:700;color:var(--neutral-900)">${d.total_quizzes_created}</div>
                        <div style="font-size:0.65rem;color:var(--neutral-400)">Quizzes</div>
                    </div>
                    <div>
                        <div style="font-size:1.25rem;font-weight:700;color:var(--neutral-900)">${d.avg_quizzes_per_mentor}</div>
                        <div style="font-size:0.65rem;color:var(--neutral-400)">Avg/Mentor</div>
                    </div>
                </div>
            </div>
            <div class="card" style="padding:20px">
                <div class="card-header" style="margin-bottom:12px;padding-bottom:10px;font-size:0.875rem">Weekly Activity <span class="badge badge-info">7 Days</span></div>
                ${weeklyHtml ? `<div style="display:flex;align-items:end;gap:8px;height:140px;padding:8px 4px">${weeklyHtml}</div>` : '<div style="text-align:center;padding:24px;color:var(--neutral-400);font-size:0.8125rem">No quiz creation activity in the last 7 days. Mentors have not created any quizzes recently.</div>'}
            </div>
        </div>
        ${d.top_mentors && d.top_mentors.length ? `
            <div class="card" style="padding:20px;margin-top:16px">
                <div class="card-header" style="margin-bottom:12px;padding-bottom:10px;font-size:0.875rem">Top Mentors by Quizzes</div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px">
                    ${d.top_mentors.map((t, i) => `
                        <div style="padding:12px 14px;background:var(--neutral-50);border-radius:var(--radius-sm);text-align:center">
                            <div style="font-size:0.75rem;font-weight:700;color:var(--brand-600)">#${i+1}</div>
                            <div style="font-size:0.8125rem;font-weight:600;margin:4px 0">${t.mentor_name}</div>
                            <div style="font-size:0.6875rem;color:var(--neutral-400)">${t.quiz_count} quizzes</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : ''}
    `;
}

// ─── ANNOUNCEMENTS ───────────────────────────────────────────────────

async function loadAnnouncements() {
    const container = document.getElementById('announcements-list');
    if (!container) return;
    const result = await apiRequest('/api/admin/announcements');
    if (!result.success) { container.innerHTML = '<div style="padding:12px;color:var(--neutral-400)">Failed to load.</div>'; return; }
    if (!result.data.length) {
        container.innerHTML = '<div style="padding:20px;text-align:center;color:var(--neutral-400);font-size:0.85rem">No announcements yet.</div>';
        return;
    }
    container.innerHTML = result.data.map(function(a) {
        return '<div style="display:flex;align-items:flex-start;gap:14px;padding:14px 0;border-bottom:1px solid var(--border-subtle)">' +
            '<div style="font-size:1.5rem;flex-shrink:0"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:24px;height:24px"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg></div>' +
            '<div style="flex:1;min-width:0">' +
                '<div style="font-weight:600;font-size:0.85rem;color:var(--neutral-800)">' + a.title + '</div>' +
                '<div style="font-size:0.8rem;color:var(--neutral-500);margin-top:4px;line-height:1.6">' + a.message + '</div>' +
                '<div style="font-size:0.65rem;color:var(--neutral-400);margin-top:6px">' + (a.created_at ? a.created_at.slice(0, 16) : '') + '</div>' +
            '</div>' +
            '<button class="btn btn-ghost btn-sm" style="color:var(--red-500);flex-shrink:0" onclick="deleteAnnouncement(' + a.announcement_id + ')">✕</button>' +
        '</div>';
    }).join('');
}

async function deleteAnnouncement(id) {
    if (!confirm('Delete this announcement?')) return;
    const result = await apiRequest('/api/admin/announcement/' + id, 'DELETE');
    if (result.success) { showAlert(result.message, 'success'); loadAnnouncements(); }
    else { showAlert(result.message, 'danger'); }
}

function showAddAnnouncement() {
    document.getElementById('ann-title').value = '';
    document.getElementById('ann-message').value = '';
    document.getElementById('ann-feedback').innerHTML = '';
    document.getElementById('announcement-modal').style.display = 'flex';
}

function closeAnnouncementModal() {
    document.getElementById('announcement-modal').style.display = 'none';
}

async function createAnnouncement() {
    const title = document.getElementById('ann-title').value.trim();
    const message = document.getElementById('ann-message').value.trim();
    if (!title || !message) {
        document.getElementById('ann-feedback').innerHTML = '<div class="alert alert-warning">Title and message required.</div>';
        return;
    }
    const result = await apiRequest('/api/admin/announcement', 'POST', { title, message });
    if (result.success) {
        document.getElementById('ann-feedback').innerHTML = '<div class="alert alert-success">Announcement posted!</div>';
        setTimeout(function() { closeAnnouncementModal(); loadAnnouncements(); }, 800);
    } else {
        document.getElementById('ann-feedback').innerHTML = '<div class="alert alert-danger">' + (result.message || 'Failed') + '</div>';
    }
}

async function loadAdminAnalytics() {
    const result = await apiRequest('/api/admin/analytics');
    if (!result.success) return;

    const d = result.data;
    const pfContainer = document.getElementById('pass-fail-stats');
    if (pfContainer) {
        const passCount = d.pass_fail.find(p => p.status === 'Pass')?.count || 0;
        const failCount = d.pass_fail.find(p => p.status === 'Fail')?.count || 0;
        const total = passCount + failCount;
        const passPct = total ? ((passCount / total) * 100) : 0;
        const failPct = total ? ((failCount / total) * 100) : 0;
        pfContainer.innerHTML = `
            <div style="padding:20px">
                <div style="display:flex;justify-content:space-between;margin-bottom:16px">
                    <div style="text-align:center;flex:1">
                        <div style="font-size:1.75rem;font-weight:700;color:var(--green-600)">${passCount}</div>
                        <div style="font-size:0.75rem;color:var(--neutral-400)">Passed</div>
                    </div>
                    <div style="width:1px;background:var(--border);margin:0 20px"></div>
                    <div style="text-align:center;flex:1">
                        <div style="font-size:1.75rem;font-weight:700;color:var(--red-600)">${failCount}</div>
                        <div style="font-size:0.75rem;color:var(--neutral-400)">Failed</div>
                    </div>
                </div>
                <div style="background:var(--neutral-100);border-radius:999px;height:28px;overflow:hidden;display:flex">
                    <div style="width:${passPct}%;background:var(--green-500);transition:width 0.5s ease"></div>
                    <div style="width:${failPct}%;background:var(--red-500);transition:width 0.5s ease"></div>
                </div>
                <div style="display:flex;justify-content:space-between;margin-top:6px;font-size:0.75rem;color:var(--neutral-400)">
                    <span>${passPct.toFixed(1)}% Pass Rate</span>
                    <span>${failPct.toFixed(1)}% Fail Rate</span>
                </div>
            </div>`;
    }

    const diffContainer = document.getElementById('difficulty-analysis');
    if (diffContainer) {
        if (!d.difficulty_analysis.length) {
            diffContainer.innerHTML = '<div style="padding:20px;text-align:center;color:var(--neutral-400);font-size:0.875rem">No data yet.</div>';
        } else {
            diffContainer.innerHTML = d.difficulty_analysis.map(diff => `
                <div style="padding:14px 16px;border-bottom:1px solid var(--border-subtle)">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                        <strong style="font-size:0.8125rem">${diff.difficulty}</strong>
                        <span class="badge ${diff.difficulty === 'Easy' ? 'badge-success' : diff.difficulty === 'Medium' ? 'badge-warning' : 'badge-danger'}">${diff.avg_accuracy}%</span>
                    </div>
                    <div style="font-size:0.75rem;color:var(--neutral-400)">${diff.attempts} attempts</div>
                </div>`).join('');
        }
    }

    const activityContainer = document.getElementById('daily-activity');
    if (activityContainer) {
        if (!d.daily_activity.length) {
            activityContainer.innerHTML = '<div style="padding:20px;text-align:center;color:var(--neutral-400);font-size:0.875rem">No activity recorded yet.</div>';
        } else {
            const sorted = [...d.daily_activity].reverse();
            const max = Math.max(...sorted.map(a => a.attempts), 1);
            activityContainer.innerHTML = `
                <div style="display:flex;align-items:end;gap:8px;height:160px;padding:24px 8px 8px">
                    ${sorted.map(a => {
                        const h = Math.max((a.attempts / max) * 130, 8);
                        const dayLabel = new Date(a.day + 'T00:00:00').toLocaleDateString('en', {weekday:'short'});
                        return `<div style="flex:1;text-align:center;height:100%;display:flex;flex-direction:column;justify-content:end">
                            <div style="background:linear-gradient(180deg,var(--brand-400),var(--brand-600));border-radius:4px 4px 0 0;height:${h}px;margin:0 auto;width:100%;max-width:36px;transition:height 0.3s ease"></div>
                            <div style="font-size:0.6rem;color:var(--neutral-400);margin-top:6px;font-weight:500">${dayLabel}</div>
                            <div style="font-size:0.65rem;color:var(--neutral-500);font-weight:600">${a.attempts}</div>
                        </div>`;
                    }).join('')}
                </div>
                <div style="text-align:center;font-size:0.65rem;color:var(--neutral-400);padding-top:8px;border-top:1px solid var(--border-subtle)">
                    Last 7 Days Activity
                </div>`;
        }
    }
}
