async function loadAdminDashboard() {
    const result = await apiRequest('/api/admin/dashboard');
    if (!result.success) return;

    const d = result.data;
    document.getElementById('total-students').textContent = d.total_students;
    document.getElementById('total-mentors').textContent = d.total_mentors;
    document.getElementById('total-quizzes').textContent = d.total_quizzes;
    document.getElementById('total-attempts').textContent = d.total_attempts;
    document.getElementById('avg-accuracy').textContent = d.avg_accuracy + '%';

    const recentStudents = document.getElementById('recent-students');
    if (recentStudents && d.recent_students.length) {
        recentStudents.innerHTML = d.recent_students.map(s => `
            <tr>
                <td>${s.name}</td>
                <td>${s.email}</td>
                <td>${s.course || 'N/A'}</td>
                <td>${s.registration_date}</td>
            </tr>
        `).join('');
    }

    const recentMentors = document.getElementById('recent-mentors');
    if (recentMentors && d.recent_mentors.length) {
        recentMentors.innerHTML = d.recent_mentors.map(m => `
            <tr>
                <td>${m.mentor_name}</td>
                <td>${m.email}</td>
                <td>${m.subject || 'N/A'}</td>
            </tr>
        `).join('');
    }

    loadAdminAnalytics();
}

async function loadStudents() {
    const result = await apiRequest('/api/admin/manage-students');
    if (!result.success) return;

    const tbody = document.querySelector('#students-table tbody');
    if (!tbody) return;

    if (!result.data.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">No students registered.</td></tr>';
        return;
    }

    tbody.innerHTML = result.data.map(s => `
        <tr>
            <td>${s.name}</td>
            <td>${s.email}</td>
            <td>${s.course || 'N/A'}</td>
            <td>${s.quiz_count || 0}</td>
            <td>${s.avg_accuracy || 0}%</td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteStudent(${s.student_id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

async function loadMentors() {
    const result = await apiRequest('/api/admin/manage-mentors');
    if (!result.success) return;

    const tbody = document.querySelector('#mentors-table tbody');
    if (!tbody) return;

    if (!result.data.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center">No mentors registered.</td></tr>';
        return;
    }

    tbody.innerHTML = result.data.map(m => `
        <tr>
            <td>${m.mentor_name}</td>
            <td>${m.email}</td>
            <td>${m.subject || 'N/A'}</td>
            <td>${m.quiz_count || 0}</td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteMentor(${m.mentor_id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

async function deleteStudent(id) {
    if (!confirm('Are you sure you want to delete this student?')) return;
    const result = await apiRequest(`/api/admin/delete-student/${id}`, 'DELETE');
    if (result.success) {
        showAlert(result.message, 'success');
        loadStudents();
    }
}

async function deleteMentor(id) {
    if (!confirm('Are you sure you want to delete this mentor?')) return;
    const result = await apiRequest(`/api/admin/delete-mentor/${id}`, 'DELETE');
    if (result.success) {
        showAlert(result.message, 'success');
        loadMentors();
    }
}

async function loadAdminAnalytics() {
    const result = await apiRequest('/api/admin/analytics');
    if (!result.success) return;

    const d = result.data;

    // Pass/Fail pie representation
    const pfContainer = document.getElementById('pass-fail-stats');
    if (pfContainer && d.pass_fail.length) {
        const total = d.pass_fail.reduce((s, p) => s + p.count, 0);
        const passPct = total ? ((d.pass_fail.find(p => p.status === 'Pass')?.count || 0) / total * 100) : 0;
        const failPct = 100 - passPct;

        pfContainer.innerHTML = `
            <div style="text-align:center;padding:20px">
                <div style="display:flex;gap:20px;justify-content:center;margin-bottom:16px">
                    <div><span style="display:inline-block;width:12px;height:12px;background:var(--success);border-radius:2px"></span> Pass: ${d.pass_fail.find(p => p.status === 'Pass')?.count || 0}</div>
                    <div><span style="display:inline-block;width:12px;height:12px;background:var(--danger);border-radius:2px"></span> Fail: ${d.pass_fail.find(p => p.status === 'Fail')?.count || 0}</div>
                </div>
                <div class="progress-bar" style="height:24px;border-radius:12px">
                    <div class="progress-fill" style="width:${passPct}%;height:24px;border-radius:12px;background:var(--success)"></div>
                </div>
                <p style="margin-top:8px;color:var(--text-light)">${passPct.toFixed(1)}% Pass Rate</p>
            </div>
        `;
    }

    // Difficulty analysis
    const diffContainer = document.getElementById('difficulty-analysis');
    if (diffContainer && d.difficulty_analysis.length) {
        diffContainer.innerHTML = d.difficulty_analysis.map(diff => `
            <div style="margin-bottom:12px;padding:12px;background:#f8fafc;border-radius:var(--radius)">
                <strong>${diff.difficulty}</strong>
                <div style="font-size:0.9rem;color:var(--text-light)">
                    Attempts: ${diff.attempts} | Avg Accuracy: ${diff.avg_accuracy}%
                </div>
            </div>
        `).join('');
    }

    // Daily activity chart
    const activityContainer = document.getElementById('daily-activity');
    if (activityContainer && d.daily_activity.length) {
        const max = Math.max(...d.daily_activity.map(a => a.attempts), 1);
        activityContainer.innerHTML = `
            <div style="display:flex;align-items:end;gap:12px;height:140px;padding:20px 0">
                ${d.daily_activity.reverse().map(a => {
                    const height = (a.attempts / max) * 120;
                    return `
                        <div style="flex:1;text-align:center">
                            <div style="background:var(--primary);border-radius:4px;height:${height}px;margin:0 auto;width:100%;min-height:4px"></div>
                            <div style="font-size:0.65rem;margin-top:4px;color:var(--text-light)">${a.day.slice(5)}</div>
                            <div style="font-size:0.6rem;color:var(--text-light)">${a.attempts}</div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }
}
