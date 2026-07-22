function escHtml(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function loadMentorDashboard() {
    const auth = await checkAuth();
    if (!auth || auth.role !== 'mentor') { window.location.href = '../login.html'; return; }
    document.getElementById('userName').textContent = auth.name;

    const result = await apiRequest('/api/mentor/dashboard');
    if (!result.success) return;

    const d = result.data;
    document.getElementById('total-quizzes').textContent = d.total_quizzes;
    document.getElementById('total-students').textContent = d.total_students;
    document.getElementById('total-attempts').textContent = d.total_attempts;
    const draftsEl = document.getElementById('total-drafts');
    if (draftsEl) draftsEl.textContent = d.draft_count || 0;
    const matEl = document.getElementById('total-materials');
    if (matEl) matEl.textContent = d.total_materials || 0;

    // Load heatmap
    loadStudentHeatmap();

    // Start live activity polling
    startLiveActivityPolling();

    // Load student list for trend chart
    loadTrendStudentList();

    // Load comparison student lists
    loadCompareStudentList();

    // Initialize calendar
    initCalendar();

    // Recent Materials
    var matContainer = document.getElementById('recent-materials');
    if (matContainer) {
        if (!d.recent_materials || !d.recent_materials.length) {
            matContainer.innerHTML = '<div class="alert alert-info">No materials uploaded yet. <a href="materials.html" style="text-decoration:underline">Upload now</a></div>';
        } else {
            matContainer.innerHTML = d.recent_materials.map(function(m) {
                var icon = m.file_type === 'link' ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>' : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
                return '<div class="card" style="margin-bottom:12px"><div class="card-header" style="margin-bottom:0"><span>' + icon + ' ' + m.title + '</span><span class="badge badge-primary">' + (m.file_type||'').toUpperCase() + '</span></div><p style="color:var(--text-light);font-size:0.85rem">' + (m.subject||'General') + ' &middot; ' + (m.created_date||'').slice(0,10) + '</p></div>';
            }).join('');
        }
    }

    const container = document.getElementById('recent-quizzes');
    if (container) {
        if (!d.recent_quizzes.length) {
            container.innerHTML = '<div class="alert alert-info">No quizzes created yet.</div>';
            return;
        }
        container.innerHTML = d.recent_quizzes.map(q => `
            <div class="card" style="margin-bottom:12px">
                <div class="card-header" style="margin-bottom:0">
                    <span>${q.topic}</span>
                    <span class="badge badge-primary">${q.difficulty}</span>
                </div>
                <p style="color:var(--text-light);font-size:0.85rem">${q.created_date}</p>
            </div>
        `).join('');
    }
}

async function loadStudentPerformance() {
    const result = await apiRequest('/api/mentor/student-performance');
    if (!result.success) return;

    const tbody = document.querySelector('#student-performance tbody');
    if (!tbody) return;
    if (!result.data.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center">No data available.</td></tr>';
        return;
    }
    tbody.innerHTML = result.data.map(s => `
        <tr>
            <td><code>${s.student_code || ''}</code></td>
            <td>${s.name}</td>
            <td>${s.email}</td>
            <td>${s.quiz_count}</td>
            <td>${s.avg_accuracy || 0}%</td>
            <td><span class="badge ${s.passed > 0 ? 'badge-success' : 'badge-danger'}">${s.passed || 0} / ${s.quiz_count || 0}</span></td>
            <td>
                <button class="btn btn-sm btn-primary" onclick="openBadgeModal(${s.student_id},'${s.name.replace(/'/g, "\\'")}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/></svg>Badge</button>
                <button class="btn btn-sm btn-success" onclick="jumpToTrend(${s.student_id})" title="View performance trend"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>Trend</button>
            </td>
            <td><button class="btn btn-sm btn-secondary" onclick="openFeedbackModal(${s.student_id},'${s.name.replace(/'/g, "\\'")}')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>Feedback</button></td>
        </tr>
    `).join('');
}

async function loadAnalytics() {
    const result = await apiRequest('/api/mentor/analytics');
    if (!result.success) return;

    const d = result.data;
    const topicContainer = document.getElementById('topic-performance');
    if (topicContainer && d.topic_performance.length) {
        topicContainer.innerHTML = d.topic_performance.map(t => {
            const barWidth = Math.min(t.avg_accuracy, 100);
            const color = t.avg_accuracy >= 60 ? 'var(--success)' : t.avg_accuracy >= 40 ? 'var(--accent)' : 'var(--danger)';
            return `
                <div style="margin-bottom:16px">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                        <span style="font-weight:500">${t.topic}</span>
                        <span>${t.avg_accuracy}% (${t.attempts} attempts)</span>
                    </div>
                    <div class="progress-bar" style="height:10px">
                        <div class="progress-fill" style="width:${barWidth}%;background:${color};height:10px"></div>
                    </div>
                </div>`;
        }).join('');
    }

    const chartContainer = document.getElementById('weekly-chart');
    if (chartContainer && d.weekly_stats.length) {
        const max = Math.max(...d.weekly_stats.map(w => w.attempts), 1);
        chartContainer.innerHTML = `
            <div style="display:flex;align-items:end;gap:12px;height:160px;padding:20px 0">
                ${d.weekly_stats.reverse().map(w => {
                    const h = (w.attempts / max) * 140;
                    return `<div style="flex:1;text-align:center">
                        <div style="background:var(--primary-light);border-radius:4px;height:${h}px;margin:0 auto;width:100%;min-height:4px"></div>
                        <div style="font-size:0.7rem;margin-top:4px;color:var(--text-light)">${w.day ? w.day.slice(5) : ''}</div>
                        <div style="font-size:0.65rem;color:var(--text-light)">${w.avg_accuracy}%</div>
                    </div>`;
                }).join('')}
            </div>`;
    }
}

// ─── MANUAL QUIZ (per-question difficulty) ───────────────────────────

let questionCount = 0;

function addQuestion() {
    const container = document.getElementById('questions-container');
    questionCount++;
    const div = document.createElement('div');
    div.className = 'card';
    div.style.marginBottom = '16px';
    div.innerHTML = `
        <div style="display:flex;justify-content:space-between;margin-bottom:12px">
            <strong>Question ${questionCount}</strong>
            <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.parentElement.remove()">Remove</button>
        </div>
        <div class="form-group"><textarea placeholder="Enter question" required style="min-height:60px;width:100%;padding:10px;border:2px solid var(--border);border-radius:var(--radius)"></textarea></div>
        <div class="grid-2">
            <div class="form-group"><label>Option A</label><input type="text" placeholder="Option A" required style="width:100%;padding:10px;border:2px solid var(--border);border-radius:var(--radius)"></div>
            <div class="form-group"><label>Option B</label><input type="text" placeholder="Option B" required style="width:100%;padding:10px;border:2px solid var(--border);border-radius:var(--radius)"></div>
            <div class="form-group"><label>Option C</label><input type="text" placeholder="Option C" required style="width:100%;padding:10px;border:2px solid var(--border);border-radius:var(--radius)"></div>
            <div class="form-group"><label>Option D</label><input type="text" placeholder="Option D" required style="width:100%;padding:10px;border:2px solid var(--border);border-radius:var(--radius)"></div>
        </div>
        <div class="grid-2">
            <div class="form-group">
                <label>Correct Answer</label>
                <select style="width:100%;padding:10px;border:2px solid var(--border);border-radius:var(--radius)">
                    <option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option>
                </select>
            </div>
            <div class="form-group">
                <label>Difficulty</label>
                <select class="q-difficulty" style="width:100%;padding:10px;border:2px solid var(--border);border-radius:var(--radius)">
                    <option value="Easy">Easy</option>
                    <option value="Medium">Medium</option>
                    <option value="Hard">Hard</option>
                    <option value="Mixed">Mixed</option>
                </select>
            </div>
        </div>`;
    container.appendChild(div);
}

async function submitManualQuiz() {
    const topic = document.getElementById('quiz-topic').value.trim();
    const subject = document.getElementById('quiz-subject').value.trim();
    const difficulty = document.getElementById('quiz-difficulty').value;

    if (!topic) { showAlert('Please enter a quiz topic.', 'warning'); return; }

    const cards = document.querySelectorAll('#questions-container .card');
    const questions = [];
    for (const card of cards) {
        const inputs = card.querySelectorAll('input, textarea, select');
        const difficulties = card.querySelectorAll('.q-difficulty');
        const q = {
            question_text: inputs[0].value.trim(),
            option_a: inputs[1].value.trim(),
            option_b: inputs[2].value.trim(),
            option_c: inputs[3].value.trim(),
            option_d: inputs[4].value.trim(),
            correct_answer: inputs[5].value,
            difficulty: difficulties.length > 0 ? difficulties[0].value : difficulty,
        };
        if (!q.question_text || !q.option_a || !q.option_b || !q.option_c || !q.option_d) {
            showAlert('Please fill in all question fields.', 'warning');
            return;
        }
        questions.push(q);
    }
    if (questions.length === 0) { showAlert('Add at least one question.', 'warning'); return; }

    const btn = document.querySelector('#manual-quiz-form button.btn-primary');
    btn.disabled = true; btn.textContent = 'Creating...';

    const result = await apiRequest('/api/mentor/create-quiz', 'POST', { topic, subject, difficulty, questions });
    btn.disabled = false; btn.textContent = 'Create Quiz';
    if (result.success) {
        var codeMsg = '';
        if (result.primary_code) {
            codeMsg = '<br><br><strong>Access Codes Generated:</strong><br>' +
                'Primary: <code style="font-weight:700;background:var(--neutral-100);padding:2px 8px;border-radius:4px">' + result.primary_code + '</code><br>' +
                'Backup: <code style="font-weight:700;background:var(--neutral-100);padding:2px 8px;border-radius:4px">' + result.backup_code + '</code>';
        }
        showAlert('Quiz published and access codes generated!' + codeMsg, 'success');
        setTimeout(() => { window.location.href = 'access-codes.html'; }, 1500);
    } else { showAlert(result.message, 'danger'); }
}

// ─── AI QUIZ (difficulty distribution) ────────────────────────────────

function updateTotalQuestions() {
    const easy = parseInt(document.getElementById('ai-easy').value) || 0;
    const medium = parseInt(document.getElementById('ai-medium').value) || 0;
    const hard = parseInt(document.getElementById('ai-hard').value) || 0;
    const total = easy + medium + hard;
    document.getElementById('ai-total-questions').textContent = total + ' total';
}

async function generateAIQuiz() {
    const topic = document.getElementById('ai-topic').value.trim();
    const subject = document.getElementById('ai-subject').value.trim();
    const numEasy = parseInt(document.getElementById('ai-easy').value) || 0;
    const numMedium = parseInt(document.getElementById('ai-medium').value) || 0;
    const numHard = parseInt(document.getElementById('ai-hard').value) || 0;

    if (!topic) { showAlert('Please enter a topic for AI quiz generation.', 'warning'); return; }
    if (numEasy + numMedium + numHard === 0) { showAlert('Please set at least 1 question.', 'warning'); return; }

    const btn = document.getElementById('ai-generate-btn');
    btn.disabled = true; btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;margin:0;display:inline-block;vertical-align:middle"></span> Generating...';

    const result = await apiRequest('/api/mentor/ai-generate-quiz', 'POST', {
        topic, subject, num_easy: numEasy, num_medium: numMedium, num_hard: numHard,
    });
    btn.disabled = false; btn.textContent = 'Generate with AI';

    const output = document.getElementById('ai-output');
    if (result.success) {
        output.innerHTML = `
            <div class="alert alert-success">${result.message}</div>
            <div class="card" style="margin-bottom:16px">
                <div class="card-header">
                    <span>Access Codes <span class="badge badge-success">Published</span></span>
                </div>
                <div style="padding:16px;display:flex;gap:16px;flex-wrap:wrap">
                    <div style="flex:1;min-width:200px;background:var(--bg-secondary);border-radius:var(--radius-md);padding:14px;text-align:center">
                        <div style="font-size:11px;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">Primary Code</div>
                        <div style="font-size:22px;font-weight:800;letter-spacing:2px;color:var(--brand-600);font-family:monospace">${result.primary_code}</div>
                    </div>
                    <div style="flex:1;min-width:200px;background:var(--bg-secondary);border-radius:var(--radius-md);padding:14px;text-align:center">
                        <div style="font-size:11px;color:var(--text-tertiary);text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">Backup Code</div>
                        <div style="font-size:22px;font-weight:800;letter-spacing:2px;color:var(--neutral-500);font-family:monospace">${result.backup_code}</div>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">Generated Questions (${result.questions.length})</div>
            ${result.questions.map((q, i) => {
                const text = q.question_text || q.question || '';
                const optA = q.option_a || (q.options && q.options[0]) || '';
                const optB = q.option_b || (q.options && q.options[1]) || '';
                const optC = q.option_c || (q.options && q.options[2]) || '';
                const optD = q.option_d || (q.options && q.options[3]) || '';
                const answer = q.correct_answer || q.correctAnswer || '';
                const diff = q.difficulty || 'Easy';
                const expl = q.explanation || '';
                return `<div style="padding:12px 0;border-bottom:1px solid var(--border)">
                    <p><strong>Q${i + 1}.</strong> ${text}</p>
                    <p style="font-size:0.85rem;color:var(--text-light)">
                        A: ${optA} | B: ${optB} | C: ${optC} | D: ${optD}<br>
                        Answer: ${answer} | Difficulty: ${diff}
                        ${expl ? `<br>Explanation: ${expl}` : ''}
                    </p>
                </div>`;
            }).join('')}
            </div>`;
    } else {
        output.innerHTML = `<div class="alert alert-danger">${result.message}</div>`;
    }
}

async function publishQuiz(quizId) {
    const result = await apiRequest(`/api/mentor/publish-quiz/${quizId}`, 'POST');
    if (result.success) {
        document.querySelectorAll('.card-header .badge-warning').forEach(el => {
            el.textContent = 'Published';
            el.className = 'badge badge-success';
        });
        document.querySelectorAll('button[onclick*="publishQuiz"]').forEach(b => {
            b.textContent = '✅ Published';
            b.disabled = true;
            b.className = 'btn btn-success btn-lg';
        });
        if (result.primary_code) {
            // Redirect to access codes page where codes are always visible full-screen
            sessionStorage.setItem('pub_quiz_id', quizId);
            sessionStorage.setItem('pub_primary', result.primary_code);
            sessionStorage.setItem('pub_backup', result.backup_code);
            window.location.href = 'access-codes.html?published=1';
        } else {
            showAlert('Quiz published!', 'success');
        }
    } else {
        showAlert(result.message, 'danger');
    }
}

async function loadMyDrafts() {
    const container = document.getElementById('drafts-container');
    if (!container) return;
    const result = await apiRequest('/api/mentor/my-drafts');
    if (!result.success || !result.data.length) {
        container.innerHTML = '<div class="alert alert-info">No draft quizzes.</div>';
        return;
    }
    container.innerHTML = result.data.map(q => `
        <div class="card" style="margin-bottom:12px">
            <div class="card-header">
                <span>${q.topic} <span class="badge badge-warning">Draft</span></span>
                <button class="btn btn-success btn-sm" onclick="publishQuiz(${q.quiz_id})"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg> Publish</button>
            </div>
            <p style="color:var(--text-light);font-size:0.85rem">${q.subject || 'General'} | ${q.created_date}</p>
        </div>
    `).join('');
}

// ─── BADGE ASSIGNMENT ────────────────────────────────────────────────

async function loadMentorBadges() {
    const container = document.getElementById('mentor-badges');
    if (!container) return;
    const result = await apiRequest('/api/mentor/badges');
    if (!result.success || !result.data.length) {
        container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;padding:12px 0">No badges assigned yet.</div>';
        return;
    }
    container.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px">' +
        result.data.map(b =>
            '<div style="text-align:center;padding:14px 8px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius)">' +
                '<div style="font-size:2rem">' + (b.badge_icon || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:32px;height:32px"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/></svg>') + '</div>' +
                '<div style="font-weight:600;font-size:0.75rem;margin-top:6px;color:var(--neutral-700)">' + b.badge_name + '</div>' +
                '<div style="font-size:0.65rem;color:var(--neutral-400);margin-top:2px">' + b.student_name + '</div>' +
            '</div>'
        ).join('') + '</div>';
}

function openBadgeModal(studentId, studentName) {
    document.getElementById('badge-student-id').value = studentId;
    document.getElementById('badge-student-name').value = studentName;
    document.getElementById('badge-name').value = '';
    document.getElementById('badge-desc').value = '';
    document.getElementById('badge-feedback').innerHTML = '';
    document.querySelectorAll('#badge-icon-picker span').forEach(el => el.classList.remove('selected'));
    document.querySelector('#badge-icon-picker span').classList.add('selected');
    document.getElementById('assign-badge-modal').style.display = 'flex';
}

function closeBadgeModal() {
    document.getElementById('assign-badge-modal').style.display = 'none';
}

async function assignBadge() {
    const studentId = document.getElementById('badge-student-id').value;
    const name = document.getElementById('badge-name').value.trim();
    const desc = document.getElementById('badge-desc').value.trim();
    const iconEl = document.querySelector('#badge-icon-picker span.selected');
    const icon = iconEl ? iconEl.getAttribute('data-icon') : 'award';

    if (!name) {
        document.getElementById('badge-feedback').innerHTML = '<div class="alert alert-danger">Please enter a badge name.</div>';
        return;
    }

    const result = await apiRequest('/api/mentor/assign-badge', 'POST', {
        student_id: parseInt(studentId),
        badge_name: name,
        badge_icon: icon,
        description: desc,
    });

    if (result.success) {
        document.getElementById('badge-feedback').innerHTML = '<div class="alert alert-success">Badge assigned successfully!</div>';
        loadMentorBadges();
        setTimeout(closeBadgeModal, 1200);
    } else {
        document.getElementById('badge-feedback').innerHTML = '<div class="alert alert-danger">' + (result.message || 'Failed to assign badge') + '</div>';
    }
}

// ─── STUDY TIME HEATMAP ──────────────────────────────────────────────

async function loadStudentHeatmap() {
    const container = document.getElementById('heatmap-container');
    if (!container) return;

    try {
        const result = await apiRequest('/api/mentor/student-heatmap');
        if (!result.success) { container.innerHTML = '<p style="color:var(--text-light)">No data available</p>'; return; }

        const data = result.data;
        const hourly = data.hourly || [];
        const studentActivity = data.student_activity || [];

        // Find peak hours
        let maxAttempts = 0;
        let peakHour = 0;
        hourly.forEach(function(h) {
            if (h.attempts > maxAttempts) { maxAttempts = h.attempts; peakHour = h.hour; }
        });

        // Build 24-hour heatmap row
        var hours = [];
        for (var i = 0; i < 24; i++) {
            var match = hourly.find(function(h) { return h.hour === i; });
            var attempts = match ? match.attempts : 0;
            hours.push({ hour: i, attempts: attempts });
        }
        var maxH = Math.max.apply(null, hours.map(function(h) { return h.attempts; })) || 1;

        var heatmapHtml = '<div style="display:flex;flex-direction:column;gap:16px">';

        // Heatmap row
        heatmapHtml += '<div style="overflow-x:auto"><div style="display:flex;gap:3px;min-width:600px">';
        hours.forEach(function(h) {
            var intensity = h.attempts / maxH;
            var bg, textColor;
            if (intensity > 0.7) { bg = 'var(--red-500)'; textColor = '#fff'; }
            else if (intensity > 0.4) { bg = 'var(--amber-400)'; textColor = 'var(--neutral-900)'; }
            else if (intensity > 0.1) { bg = 'var(--brand-200)'; textColor = 'var(--neutral-900)'; }
            else { bg = 'var(--neutral-100)'; textColor = 'var(--neutral-500)'; }
            var label = h.hour === 0 ? '12a' : h.hour < 12 ? h.hour + 'a' : h.hour === 12 ? '12p' : (h.hour - 12) + 'p';
            heatmapHtml += '<div title="' + label + ': ' + h.attempts + ' attempts" style="flex:1;min-width:24px;height:48px;border-radius:4px;background:' + bg + ';color:' + textColor + ';display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:0.65rem;cursor:default;transition:transform 0.15s" onmouseover="this.style.transform=\'scale(1.1)\'" onmouseout="this.style.transform=\'scale(1)\'">';
            heatmapHtml += '<span style="font-weight:600">' + h.attempts + '</span>';
            heatmapHtml += '<span style="opacity:0.8;font-size:0.55rem">' + label + '</span>';
            heatmapHtml += '</div>';
        });
        heatmapHtml += '</div></div>';

        // Legend + peak info
        heatmapHtml += '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:16px;font-size:0.75rem">';
        heatmapHtml += '<div style="display:flex;align-items:center;gap:6px"><span style="width:14px;height:14px;border-radius:3px;background:var(--red-500);display:inline-block"></span><span style="color:var(--text-light)">High</span></div>';
        heatmapHtml += '<div style="display:flex;align-items:center;gap:6px"><span style="width:14px;height:14px;border-radius:3px;background:var(--amber-400);display:inline-block"></span><span style="color:var(--text-light)">Medium</span></div>';
        heatmapHtml += '<div style="display:flex;align-items:center;gap:6px"><span style="width:14px;height:14px;border-radius:3px;background:var(--brand-200);display:inline-block"></span><span style="color:var(--text-light)">Low</span></div>';
        heatmapHtml += '<div style="display:flex;align-items:center;gap:6px"><span style="width:14px;height:14px;border-radius:3px;background:var(--neutral-100);display:inline-block;border:1px solid var(--neutral-200)"></span><span style="color:var(--text-light)">None</span></div>';
        if (maxAttempts > 0) {
            var peakLabel = peakHour === 0 ? '12 AM' : peakHour < 12 ? peakHour + ' AM' : peakHour === 12 ? '12 PM' : (peakHour - 12) + ' PM';
            heatmapHtml += '<div style="margin-left:auto;color:var(--brand-600);font-weight:600">Peak: ' + peakLabel + ' (' + maxAttempts + ' attempts)</div>';
        }
        heatmapHtml += '</div>';

        // Top active students table
        if (studentActivity.length > 0) {
            heatmapHtml += '<div style="margin-top:8px;border-top:1px solid var(--neutral-100);padding-top:12px">';
            heatmapHtml += '<div style="font-weight:600;font-size:0.8rem;margin-bottom:8px;color:var(--neutral-700)">Top Active Students</div>';
            heatmapHtml += '<div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(200px, 1fr));gap:6px">';
            studentActivity.slice(0, 6).forEach(function(s) {
                var initials = s.name.split(' ').map(function(w) { return w[0]; }).join('').substring(0, 2);
                heatmapHtml += '<div style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:var(--neutral-50);border-radius:6px;font-size:0.75rem">';
                heatmapHtml += '<div style="width:28px;height:28px;border-radius:50%;background:var(--brand-100);color:var(--brand-600);display:flex;align-items:center;justify-content:center;font-weight:600;font-size:0.65rem">' + initials + '</div>';
                heatmapHtml += '<div style="flex:1;min-width:0"><div style="font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + escHtml(s.name) + '</div>';
                heatmapHtml += '<div style="color:var(--text-light);font-size:0.65rem">' + s.total_attempts + ' quizzes · ' + s.avg_accuracy + '%</div></div>';
                heatmapHtml += '</div>';
            });
            heatmapHtml += '</div></div>';
        }

        heatmapHtml += '</div>';
        container.innerHTML = heatmapHtml;

    } catch (e) {
        container.innerHTML = '<p style="color:var(--text-light)">Could not load heatmap data</p>';
    }
}

// ─── LIVE STUDENT ACTIVITY ────────────────────────────────────────────

var liveActivityInterval = null;

async function loadLiveActivity() {
    try {
        var result = await apiRequest('/api/mentor/live-activity');
        if (!result.success) return;
        var d = result.data;

        document.getElementById('live-active').textContent = d.active_count;
        document.getElementById('live-finished').textContent = d.finished_count;
        document.getElementById('live-starts').textContent = d.started_count;

        var logEl = document.getElementById('activity-log');
        if (!logEl) return;

        if (!d.activity_log || d.activity_log.length === 0) {
            logEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-light);font-size:0.8rem">No recent activity</div>';
            return;
        }

        logEl.innerHTML = d.activity_log.map(function(a) {
            var time = a.date ? a.date.split(' ')[1] || a.date.split('T')[1] || '' : '';
            if (time.length > 8) time = time.substring(0, 8);
            var dotColor, actionText;
            if (a.action === 'finished') {
                if (a.status === 'Pass') {
                    dotColor = 'var(--green-500)';
                    actionText = 'Passed "' + escHtml(a.topic) + '" (' + a.accuracy + '%)';
                } else {
                    dotColor = 'var(--red-500)';
                    actionText = 'Failed "' + escHtml(a.topic) + '" (' + a.accuracy + '%)';
                }
            } else if (a.action === 'tab_switch') {
                dotColor = 'var(--red-500)';
                actionText = 'Tab switch on "' + escHtml(a.topic) + '"';
            } else if (a.action === 'devtools' || a.action === 'print_screen') {
                dotColor = 'var(--red-500)';
                actionText = 'Security: ' + a.action.replace('_', ' ');
            } else if (a.action === 'copy_paste') {
                dotColor = 'var(--red-500)';
                actionText = 'Copy/paste attempt on "' + escHtml(a.topic) + '"';
            } else {
                dotColor = 'var(--amber-500)';
                actionText = 'Active on "' + escHtml(a.topic) + '"';
            }
            return '<div class="activity-item">' +
                '<span class="activity-dot" style="background:' + dotColor + '"></span>' +
                '<span style="color:var(--text-light);font-size:0.7rem;min-width:60px;font-variant-numeric:tabular-nums">' + time + '</span>' +
                '<span style="font-weight:500;min-width:100px">' + escHtml(a.name) + '</span>' +
                '<span style="color:var(--text-light)">' + actionText + '</span>' +
                '</div>';
        }).join('');
    } catch (e) { /* silent fail for polling */ }
}

function startLiveActivityPolling() {
    loadLiveActivity();
    if (liveActivityInterval) clearInterval(liveActivityInterval);
    liveActivityInterval = setInterval(loadLiveActivity, 8000);
}

// ─── PERFORMANCE TREND CHART ──────────────────────────────────────────

var trendChart = null;

async function loadTrendStudentList() {
    try {
        var result = await apiRequest('/api/mentor/students');
        if (!result.success) return;
        var select = document.getElementById('trend-student-select');
        if (!select) return;
        result.data.forEach(function(s) {
            var opt = document.createElement('option');
            opt.value = s.student_id;
            opt.textContent = s.name + ' (' + s.student_code + ')';
            select.appendChild(opt);
        });
    } catch (e) { /* silent */ }
}

function jumpToTrend(studentId) {
    var select = document.getElementById('trend-student-select');
    if (select) {
        select.value = studentId;
        loadPerformanceTrend(studentId);
    }
    // Scroll to trend card
    var trendCard = document.getElementById('trend-container');
    if (trendCard) trendCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

async function loadPerformanceTrend(studentId) {
    var container = document.getElementById('trend-container');
    if (!container) return;
    if (!studentId) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-light);font-size:0.85rem;padding-top:80px">Select a student to view performance trend</div>';
        if (trendChart) { trendChart.destroy(); trendChart = null; }
        return;
    }

    try {
        var result = await apiRequest('/api/mentor/student-trend/' + studentId);
        if (!result.success) { container.innerHTML = '<div style="text-align:center;color:var(--text-light);font-size:0.85rem;padding-top:80px">No data for this student</div>'; return; }

        var data = result.data;
        var results = data.results;
        var insights = data.insights;

        if (!results || results.length === 0) {
            container.innerHTML = '<div style="text-align:center;color:var(--text-light);font-size:0.85rem;padding-top:80px">No quiz results for this student</div>';
            return;
        }

        // Build chart data
        var labels = results.map(function(r) {
            var d = r.date.split(' ')[0] || r.date.split('T')[0];
            return d.substring(5); // MM-DD
        });
        var scores = results.map(function(r) { return r.accuracy; });
        var topics = results.map(function(r) { return r.topic; });

        // Trend direction icon
        var trendIcon, trendColor, trendText;
        if (insights.trend_direction === 'improving') {
            trendIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="var(--green-500)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>';
            trendColor = 'var(--green-500)';
            trendText = 'Improving (+' + insights.improvement + '%)';
        } else if (insights.trend_direction === 'declining') {
            trendIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="var(--red-500)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/></svg>';
            trendColor = 'var(--red-500)';
            trendText = 'Declining (' + insights.improvement + '%)';
        } else {
            trendIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="var(--amber-500)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><line x1="5" y1="12" x2="19" y2="12"/></svg>';
            trendColor = 'var(--amber-500)';
            trendText = 'Stable';
        }

        // Insights HTML
        var insightsHtml = '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px;font-size:0.75rem">';
        insightsHtml += '<div style="padding:6px 10px;background:var(--neutral-50);border-radius:6px"><strong>' + insights.total_quizzes + '</strong> quizzes</div>';
        insightsHtml += '<div style="padding:6px 10px;background:var(--neutral-50);border-radius:6px">Avg: <strong>' + insights.avg_score + '%</strong></div>';
        insightsHtml += '<div style="padding:6px 10px;background:var(--neutral-50);border-radius:6px">Best: <strong style="color:var(--green-500)">' + insights.best_score + '%</strong></div>';
        insightsHtml += '<div style="padding:6px 10px;background:var(--neutral-50);border-radius:6px">Low: <strong style="color:var(--red-500)">' + insights.worst_score + '%</strong></div>';
        insightsHtml += '<div style="padding:6px 10px;border-radius:6px;display:flex;align-items:center;gap:4px;background:' + (insights.trend_direction === 'improving' ? 'rgba(34,197,94,0.1)' : insights.trend_direction === 'declining' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)') + '">' + trendIcon + ' <span style="color:' + trendColor + ';font-weight:600">' + trendText + '</span></div>';
        insightsHtml += '</div>';

        container.innerHTML = insightsHtml + '<div style="position:relative;height:220px"><canvas id="trend-canvas"></canvas></div>';

        // Render chart
        var ctx = document.getElementById('trend-canvas').getContext('2d');
        if (trendChart) trendChart.destroy();
        trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Score %',
                    data: scores,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99,102,241,0.1)',
                    borderWidth: 2.5,
                    pointRadius: 4,
                    pointBackgroundColor: '#6366f1',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    tension: 0.3,
                    fill: true,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            afterLabel: function(ctx) { return 'Topic: ' + topics[ctx.dataIndex]; }
                        }
                    }
                },
                scales: {
                    y: { beginAtZero: true, max: 100, ticks: { callback: function(v) { return v + '%'; }, font: { size: 11 } }, grid: { color: 'rgba(0,0,0,0.04)' } },
                    x: { ticks: { font: { size: 10 } }, grid: { display: false } }
                }
            }
        });

    } catch (e) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-light);font-size:0.85rem;padding-top:80px">Could not load trend data</div>';
    }
}

// ─── STUDENT COMPARISON ───────────────────────────────────────────────

function loadCompareStudentList() {
    apiRequest('/api/mentor/students').then(function(result) {
        if (!result.success) return;
        ['compare-a', 'compare-b'].forEach(function(id) {
            var sel = document.getElementById(id);
            if (!sel) return;
            result.data.forEach(function(s) {
                var opt = document.createElement('option');
                opt.value = s.student_id;
                opt.textContent = s.name + ' (' + s.student_code + ')';
                sel.appendChild(opt);
            });
        });
    });
}

async function loadComparison() {
    var aId = document.getElementById('compare-a').value;
    var bId = document.getElementById('compare-b').value;
    var container = document.getElementById('comparison-container');
    if (!container) return;

    if (!aId || !bId) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-light);font-size:0.85rem;padding:40px 0">Select two students to compare</div>';
        return;
    }

    try {
        var result = await apiRequest('/api/mentor/compare-students', 'POST', { student_a: parseInt(aId), student_b: parseInt(bId) });
        if (!result.success) { container.innerHTML = '<div style="text-align:center;color:var(--red-500);font-size:0.85rem;padding:40px 0">' + escHtml(result.message) + '</div>'; return; }

        var d = result.data;
        var sa = d.a, sb = d.b;
        if (!sa.stats || !sb.stats) {
            container.innerHTML = '<div style="text-align:center;color:var(--text-light);font-size:0.85rem;padding:40px 0">One or both students have no quiz data</div>';
            return;
        }
        var w = d.winners;

        function medal(metric, side) {
            if (w[metric] === side) return ' <span style="color:var(--amber-500);font-size:0.75rem" title="Winner">Winner</span>';
            return '';
        }

        var rows = [
            { label: 'Avg Accuracy', a: sa.stats.avg_accuracy + '%', b: sb.stats.avg_accuracy + '%', metric: 'avg_accuracy' },
            { label: 'Quizzes Taken', a: sa.stats.total_quizzes, b: sb.stats.total_quizzes, metric: 'total_quizzes' },
            { label: 'Best Score', a: sa.stats.best_score + '%', b: sb.stats.best_score + '%', metric: 'best_score' },
            { label: 'Worst Score', a: sa.stats.worst_score + '%', b: sb.stats.worst_score + '%', metric: null },
            { label: 'Improvement', a: (sa.stats.improvement >= 0 ? '+' : '') + sa.stats.improvement + '%', b: (sb.stats.improvement >= 0 ? '+' : '') + sb.stats.improvement + '%', metric: 'improvement' },
            { label: 'Avg Time', a: sa.stats.avg_time + 's', b: sb.stats.avg_time + 's', metric: 'avg_time' },
            { label: 'Pass / Fail', a: sa.stats.passed + ' / ' + sa.stats.failed, b: sb.stats.passed + ' / ' + sb.stats.failed, metric: null },
        ];

        var html = '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:0.8rem">';
        html += '<thead><tr style="border-bottom:2px solid var(--neutral-100)">';
        html += '<th style="text-align:left;padding:8px;color:var(--text-light)">Stat</th>';
        html += '<th style="text-align:center;padding:8px;color:var(--brand-600);font-weight:600">' + escHtml(sa.info.name) + '</th>';
        html += '<th style="text-align:center;padding:8px;color:var(--brand-600);font-weight:600">' + escHtml(sb.info.name) + '</th>';
        html += '</tr></thead><tbody>';

        rows.forEach(function(r) {
            var aWin = w[r.metric] === 'a';
            var bWin = w[r.metric] === 'b';
            html += '<tr style="border-bottom:1px solid var(--neutral-50)">';
            html += '<td style="padding:8px;color:var(--text-light)">' + r.label + '</td>';
            html += '<td style="text-align:center;padding:8px;font-weight:' + (aWin ? '700' : '400') + ';color:' + (aWin ? 'var(--green-600)' : 'inherit') + '">' + r.a + medal(r.metric, 'a') + '</td>';
            html += '<td style="text-align:center;padding:8px;font-weight:' + (bWin ? '700' : '400') + ';color:' + (bWin ? 'var(--green-600)' : 'inherit') + '">' + r.b + medal(r.metric, 'b') + '</td>';
            html += '</tr>';
        });
        html += '</tbody></table></div>';

        // Winner summary
        var aWins = Object.values(w).filter(function(v) { return v === 'a'; }).length;
        var bWins = Object.values(w).filter(function(v) { return v === 'b'; }).length;
        html += '<div style="margin-top:12px;padding:10px 12px;background:var(--neutral-50);border-radius:6px;font-size:0.75rem;display:flex;gap:16px;align-items:center">';
        html += '<span style="font-weight:600">' + escHtml(sa.info.name) + ' wins <strong style="color:var(--green-600)">' + aWins + '</strong> metrics</span>';
        html += '<span style="color:var(--neutral-300)">|</span>';
        html += '<span style="font-weight:600">' + escHtml(sb.info.name) + ' wins <strong style="color:var(--green-600)">' + bWins + '</strong> metrics</span>';
        if (aWins > bWins) {
            html += '<span style="margin-left:auto;color:var(--green-600);font-weight:600">Better overall: ' + escHtml(sa.info.name) + '</span>';
        } else if (bWins > aWins) {
            html += '<span style="margin-left:auto;color:var(--green-600);font-weight:600">Better overall: ' + escHtml(sb.info.name) + '</span>';
        } else {
            html += '<span style="margin-left:auto;color:var(--amber-600);font-weight:600">Evenly matched!</span>';
        }
        html += '</div>';

        container.innerHTML = html;

    } catch (e) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-light);font-size:0.85rem;padding:40px 0">Could not load comparison</div>';
    }
}

// ─── CALENDAR ACTIVITY ────────────────────────────────────────────────

var calendarMonth, calendarYear;

function initCalendar() {
    var now = new Date();
    calendarMonth = now.getMonth() + 1;
    calendarYear = now.getFullYear();
    loadCalendar();
}

function changeCalendarMonth(delta) {
    calendarMonth += delta;
    if (calendarMonth > 12) { calendarMonth = 1; calendarYear++; }
    if (calendarMonth < 1) { calendarMonth = 12; calendarYear--; }
    loadCalendar();
}

async function loadCalendar() {
    var container = document.getElementById('calendar-container');
    var label = document.getElementById('calendar-month-label');
    if (!container) return;

    var monthNames = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    if (label) label.textContent = monthNames[calendarMonth] + ' ' + calendarYear;

    try {
        var result = await apiRequest('/api/mentor/calendar-activity?month=' + calendarMonth + '&year=' + calendarYear);
        if (!result.success) { container.innerHTML = '<p style="color:var(--text-light);font-size:0.85rem;text-align:center">No data</p>'; return; }

        var cal = result.data.calendar;
        var firstDay = new Date(calendarYear, calendarMonth - 1, 1).getDay();
        var daysInMonth = new Date(calendarYear, calendarMonth, 0).getDate();

        var html = '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center">';
        var dayHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        dayHeaders.forEach(function(d) {
            html += '<div style="padding:6px 0;font-size:0.65rem;font-weight:600;color:var(--text-light);text-transform:uppercase">' + d + '</div>';
        });

        // Empty cells before first day
        for (var i = 0; i < firstDay; i++) {
            html += '<div style="min-height:56px"></div>';
        }

        // Day cells
        var totalQuizzes = 0, totalPassed = 0, totalFailed = 0;
        var mostActiveDay = 0, mostActiveCount = 0;

        for (var day = 1; day <= daysInMonth; day++) {
            var dateStr = calendarYear + '-' + String(calendarMonth).padStart(2, '0') + '-' + String(day).padStart(2, '0');
            var data = cal[dateStr];
            var dayTotal = data ? data.total : 0;
            var dayPassed = data ? data.passed : 0;
            var dayFailed = data ? data.failed : 0;
            totalQuizzes += dayTotal;
            totalPassed += dayPassed;
            totalFailed += dayFailed;
            if (dayTotal > mostActiveCount) { mostActiveCount = dayTotal; mostActiveDay = day; }

            var bg = 'transparent';
            var dotColor = '';
            if (dayTotal > 0) {
                if (dayFailed > 0) { bg = 'rgba(239,68,68,0.08)'; dotColor = 'var(--red-500)'; }
                else { bg = 'rgba(34,197,94,0.08)'; dotColor = 'var(--green-500)'; }
            }

            html += '<div style="min-height:56px;padding:4px;border-radius:4px;background:' + bg + ';cursor:default;position:relative" title="' + dateStr + ': ' + dayTotal + ' quizzes">';
            html += '<div style="font-size:0.7rem;font-weight:500;color:var(--neutral-700)">' + day + '</div>';
            if (dayTotal > 0) {
                html += '<div style="display:flex;justify-content:center;gap:2px;margin-top:2px">';
                html += '<span style="width:6px;height:6px;border-radius:50%;background:' + dotColor + '"></span>';
                html += '</div>';
                html += '<div style="font-size:0.6rem;color:var(--text-light);margin-top:2px">' + dayTotal + '</div>';
            }
            html += '</div>';
        }

        html += '</div>';

        // Legend + stats
        html += '<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--neutral-100);display:flex;flex-wrap:wrap;gap:12px;font-size:0.7rem;align-items:center">';
        html += '<div style="display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:var(--green-500)"></span> Passed</div>';
        html += '<div style="display:flex;align-items:center;gap:4px"><span style="width:8px;height:8px;border-radius:50%;background:var(--red-500)"></span> Failed</div>';
        html += '<span style="color:var(--neutral-300)">|</span>';
        html += '<span>Total: <strong>' + totalQuizzes + '</strong></span>';
        html += '<span>Passed: <strong style="color:var(--green-600)">' + totalPassed + '</strong></span>';
        html += '<span>Failed: <strong style="color:var(--red-500)">' + totalFailed + '</strong></span>';
        if (mostActiveDay > 0) {
            html += '<span style="margin-left:auto;color:var(--brand-600);font-weight:500">Most active: day ' + mostActiveDay + ' (' + mostActiveCount + ' quizzes)</span>';
        }
        html += '</div>';

        container.innerHTML = html;

    } catch (e) {
        container.innerHTML = '<p style="color:var(--text-light);font-size:0.85rem;text-align:center">Could not load calendar</p>';
    }
}

// ─── STUDENT LEADERBOARD ──────────────────────────────────────────────

async function loadLeaderboard() {
    var container = document.getElementById('leaderboard-container');
    if (!container) return;

    try {
        var result = await apiRequest('/api/mentor/leaderboard');
        if (!result.success) { container.innerHTML = '<p style="color:var(--text-light);text-align:center;padding:40px">No data available</p>'; return; }

        var data = result.data;
        var lb = data.leaderboard;
        var stats = data.stats;

        // Update stat cards
        var totalEl = document.getElementById('lb-total');
        var avgEl = document.getElementById('lb-avg');
        var topEl = document.getElementById('lb-top');
        var lowEl = document.getElementById('lb-low');
        if (totalEl) totalEl.textContent = stats.total_students;
        if (avgEl) avgEl.textContent = stats.avg_score + '%';
        if (topEl) topEl.textContent = stats.top_score + '%';
        if (lowEl) lowEl.textContent = stats.low_score + '%';

        if (!lb || lb.length === 0) {
            container.innerHTML = '<p style="color:var(--text-light);text-align:center;padding:40px">No student data yet</p>';
            return;
        }

        var html = '';

        // Header
        html += '<div class="lb-row lb-header">';
        html += '<div>Rank</div>';
        html += '<div>Student</div>';
        html += '<div style="text-align:center">Avg Accuracy</div>';
        html += '<div style="text-align:center">Quizzes</div>';
        html += '<div style="text-align:center">Best</div>';
        html += '<div style="text-align:center">Last</div>';
        html += '</div>';

        // Rows
        lb.forEach(function(s) {
            var rankClass = s.rank <= 3 ? 'rank-' + s.rank : 'rank-other';
            var rankIcon = s.rank === 1 ? '🥇' : s.rank === 2 ? '🥈' : s.rank === 3 ? '🥉' : s.rank;
            var isTop3 = s.rank <= 3;

            html += '<div class="lb-row" style="' + (isTop3 ? 'background:rgba(99,102,241,0.03)' : '') + '">';
            html += '<div><span class="rank-badge ' + rankClass + '">' + rankIcon + '</span></div>';
            html += '<div>';
            html += '<div style="font-weight:600;font-size:0.85rem">' + escHtml(s.name) + '</div>';
            html += '<div style="font-size:0.7rem;color:var(--text-light)">' + escHtml(s.student_code || '') + '</div>';
            html += '</div>';
            html += '<div style="text-align:center">';
            html += '<span style="font-weight:700;color:' + (s.avg_accuracy >= 70 ? 'var(--green-600)' : s.avg_accuracy >= 50 ? 'var(--amber-600)' : 'var(--red-500)') + '">' + s.avg_accuracy + '%</span>';
            html += '</div>';
            html += '<div style="text-align:center;color:var(--text-light)">' + s.total_quizzes + '</div>';
            html += '<div style="text-align:center;color:var(--green-600);font-weight:500">' + s.best_score + '%</div>';
            html += '<div style="text-align:center;color:var(--text-light)">' + s.last_score + '%</div>';
            html += '</div>';
        });

        // Summary bar
        html += '<div style="padding:16px;background:var(--neutral-50);border-top:2px solid var(--neutral-100);display:flex;flex-wrap:wrap;gap:20px;font-size:0.8rem">';
        html += '<div>Total students: <strong>' + stats.total_students + '</strong></div>';
        html += '<div>Avg score: <strong>' + stats.avg_score + '%</strong></div>';
        html += '<div>Top: <strong style="color:var(--green-600)">' + stats.top_name + ' (' + stats.top_score + '%)</strong></div>';
        html += '<div>Lowest: <strong style="color:var(--red-500)">' + stats.low_name + ' (' + stats.low_score + '%)</strong></div>';
        html += '</div>';

        container.innerHTML = html;

    } catch (e) {
        container.innerHTML = '<p style="color:var(--text-light);text-align:center;padding:40px">Could not load leaderboard</p>';
    }
}

// Icon picker
document.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('click', function(e) {
        if (e.target.closest('#badge-icon-picker span')) {
            document.querySelectorAll('#badge-icon-picker span').forEach(el => el.classList.remove('selected'));
            e.target.closest('#badge-icon-picker span').classList.add('selected');
        }
    });
});

// ─── FEEDBACK ─────────────────────────────────────────────────────────

function openFeedbackModal(studentId, studentName) {
    document.getElementById('feedback-student-id').value = studentId;
    document.getElementById('feedback-student-name').value = studentName;
    document.getElementById('feedback-comment').value = '';
    document.getElementById('feedback-rating').value = 0;
    document.querySelectorAll('#star-rating span').forEach(el => el.classList.remove('active'));
    document.getElementById('feedback-feedback').innerHTML = '';
    document.getElementById('feedback-modal').style.display = 'flex';
}

function closeFeedbackModal() {
    document.getElementById('feedback-modal').style.display = 'none';
}

async function submitFeedback() {
    const studentId = document.getElementById('feedback-student-id').value;
    const rating = parseInt(document.getElementById('feedback-rating').value);
    const comment = document.getElementById('feedback-comment').value.trim();

    if (!rating || rating < 1) {
        document.getElementById('feedback-feedback').innerHTML = '<div class="alert alert-danger">Please select a star rating.</div>';
        return;
    }

    const result = await apiRequest('/api/mentor/submit-feedback', 'POST', {
        student_id: parseInt(studentId),
        rating: rating,
        comment: comment,
    });

    if (result.success) {
        document.getElementById('feedback-feedback').innerHTML = '<div class="alert alert-success">Feedback submitted successfully!</div>';
        setTimeout(closeFeedbackModal, 1200);
    } else {
        document.getElementById('feedback-feedback').innerHTML = '<div class="alert alert-danger">' + (result.message || 'Failed to submit feedback') + '</div>';
    }
}

// Star rating handler
document.addEventListener('click', function(e) {
    var star = e.target.closest('#star-rating span');
    if (star) {
        var rating = parseInt(star.getAttribute('data-star'));
        document.getElementById('feedback-rating').value = rating;
        document.querySelectorAll('#star-rating span').forEach(function(el) {
            var s = parseInt(el.getAttribute('data-star'));
            el.classList.toggle('active', s <= rating);
        });
    }
});

// ─── ANNOUNCEMENTS ───────────────────────────────────────────────────

async function loadMentorAnnouncements() {
    const container = document.getElementById('mentor-announcements');
    if (!container) return;
    const result = await apiRequest('/api/announcements');
    if (!result || !result.success || !result.data.length) { container.innerHTML = ''; return; }
    container.innerHTML = '<div class="card" style="background:linear-gradient(135deg,var(--brand-50),#eef2ff);border-color:var(--brand-200)">' +
        '<div class="card-header" style="border-bottom-color:var(--brand-100);padding-bottom:10px;margin-bottom:10px;justify-content:flex-start;gap:6px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;flex-shrink:0"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg><span>Announcements</span></div>' +
        result.data.map(function(a) {
            return '<div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--brand-100)">' +
                '<div style="flex:1">' +
                    '<div style="font-weight:600;font-size:0.85rem;color:var(--neutral-800)">' + a.title + '</div>' +
                    '<div style="font-size:0.8rem;color:var(--neutral-500);margin-top:2px;line-height:1.6">' + a.message + '</div>' +
                    '<div style="font-size:0.6rem;color:var(--neutral-400);margin-top:4px">' + (a.created_at ? a.created_at.slice(0, 16) : '') + '</div>' +
                '</div>' +
            '</div>';
        }).join('') +
    '</div>';
}

// ─── QUIZZES MANAGEMENT ──────────────────────────────────────────────

async function loadMentorQuizzes() {
    const auth = await checkAuth();
    if (!auth || auth.role !== 'mentor') { window.location.href = '../login.html'; return; }

    const result = await apiRequest('/api/mentor/quizzes');
    if (!result.success) return;

    const quizzes = result.data;
    const tbody = document.getElementById('quizzes-tbody');
    if (!tbody) return;

    if (!quizzes.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--neutral-400);padding:40px">No quizzes created yet. <a href="create-quiz.html">Create your first quiz</a></td></tr>';
        document.getElementById('qtotal').textContent = '0';
        document.getElementById('qpublished').textContent = '0';
        document.getElementById('qdrafts').textContent = '0';
        document.getElementById('qquestions').textContent = '0';
        return;
    }

    var stats = { total: quizzes.length, published: 0, drafts: 0, questions: 0 };
    quizzes.forEach(function(q) {
        if (q.status === 'published') stats.published++;
        else stats.drafts++;
        stats.questions += (q.question_count || 0);
    });
    document.getElementById('qtotal').textContent = stats.total;
    document.getElementById('qpublished').textContent = stats.published;
    document.getElementById('qdrafts').textContent = stats.drafts;
    document.getElementById('qquestions').textContent = stats.questions;

    tbody.innerHTML = quizzes.map(function(q) {
        var isDraft = q.status === 'draft';
        var statusHtml = isDraft
            ? '<span class="quiz-status"><span class="dot dft"></span> Draft</span>'
            : '<span class="quiz-status"><span class="dot pub"></span> Published</span>';
        var actions = '<button class="action-btn edit" onclick="loadQuizForEdit(' + q.quiz_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>Edit</button> ';
        actions += '<button class="action-btn delete" onclick="openDeleteModal(' + q.quiz_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>Delete</button>';
        if (!isDraft && q.status === 'published') {
            actions += ' <button class="action-btn report" onclick="generateQuizReport(' + q.quiz_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>Report</button>';
        }
        if (isDraft) {
            actions += ' <button class="action-btn publish" onclick="publishQuizFromList(' + q.quiz_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg> Publish</button>';
        }
        return '<tr>' +
            '<td><strong>' + q.topic + '</strong></td>' +
            '<td>' + (q.subject || 'General') + '</td>' +
            '<td><span class="badge badge-primary">' + q.difficulty + '</span></td>' +
            '<td>' + statusHtml + '</td>' +
            '<td>' + (q.question_count || 0) + '</td>' +
            '<td style="font-size:0.75rem;color:var(--neutral-400)">' + (q.created_date ? q.created_date.slice(0, 10) : '-') + '</td>' +
            '<td>' + actions + '</td>' +
            '</tr>';
    }).join('');
}

async function publishQuizFromList(quizId) {
    var btn = event.target;
    btn.disabled = true; btn.textContent = 'Publishing...';
    const result = await apiRequest('/api/mentor/publish-quiz/' + quizId, 'POST');
    if (result.success) {
        if (result.primary_code) {
            sessionStorage.setItem('pub_quiz_id', quizId);
            sessionStorage.setItem('pub_primary', result.primary_code);
            sessionStorage.setItem('pub_backup', result.backup_code);
            window.location.href = 'access-codes.html?published=1';
        } else {
            showAlert('Quiz published!', 'success');
        }
    } else {
        showAlert(result.message, 'danger');
        btn.disabled = false; btn.textContent = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg> Publish';
    }
}

function openDeleteModal(quizId) {
    document.getElementById('delete-quiz-id').value = quizId;
    document.getElementById('delete-feedback').innerHTML = '';
    document.getElementById('delete-modal').style.display = 'flex';
}

function closeDeleteModal() {
    document.getElementById('delete-modal').style.display = 'none';
}

async function confirmDeleteQuiz() {
    var quizId = document.getElementById('delete-quiz-id').value;
    var btn = document.querySelector('#delete-modal .btn-danger');
    btn.disabled = true; btn.textContent = 'Deleting...';
    const result = await apiRequest('/api/mentor/quiz/' + quizId, 'DELETE');
    if (result.success) {
        document.getElementById('delete-feedback').innerHTML = '<div class="alert alert-success">Quiz deleted!</div>';
        setTimeout(function() { closeDeleteModal(); loadMentorQuizzes(); }, 800);
    } else {
        document.getElementById('delete-feedback').innerHTML = '<div class="alert alert-danger">' + (result.message || 'Failed to delete') + '</div>';
        btn.disabled = false; btn.textContent = 'Delete';
    }
}

var editQuestionCount = 0;

async function loadQuizForEdit(quizId) {
    document.getElementById('edit-feedback').innerHTML = '';
    document.getElementById('edit-quiz-id').value = quizId;
    document.getElementById('edit-questions-container').innerHTML = '<div class="loading" style="padding:20px"><div class="spinner"></div></div>';
    document.getElementById('edit-modal').style.display = 'flex';

    const result = await apiRequest('/api/mentor/quiz/' + quizId);
    if (!result.success) {
        document.getElementById('edit-questions-container').innerHTML = '<div class="alert alert-danger">Failed to load quiz.</div>';
        return;
    }

    var q = result.data.quiz;
    document.getElementById('edit-topic').value = q.topic;
    document.getElementById('edit-subject').value = q.subject || '';
    document.getElementById('edit-difficulty').value = q.difficulty;

    var container = document.getElementById('edit-questions-container');
    container.innerHTML = '';
    editQuestionCount = 0;
    result.data.questions.forEach(function(qst) {
        addEditQuestion(qst);
    });
    if (result.data.questions.length === 0) addEditQuestion();
}

function addEditQuestion(data) {
    editQuestionCount++;
    var container = document.getElementById('edit-questions-container');
    var num = editQuestionCount;
    var q = data || { question_text: '', option_a: '', option_b: '', option_c: '', option_d: '', correct_answer: 'A', difficulty: 'Easy' };
    var div = document.createElement('div');
    div.className = 'card';
    div.style.marginBottom = '12px';
    div.style.padding = '16px';
    div.id = 'eq-' + num;
    div.innerHTML = '<div style="display:flex;justify-content:space-between;margin-bottom:10px">' +
        '<strong style="font-size:0.85rem">Q' + num + '</strong>' +
        '<button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.parentElement.remove()">Remove</button></div>' +
        '<div class="form-group" style="margin-bottom:10px"><textarea placeholder="Question text" style="min-height:50px;width:100%;padding:8px 10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-family:var(--font);font-size:0.8125rem">' + q.question_text + '</textarea></div>' +
        '<div class="grid-2" style="gap:10px;margin-bottom:10px">' +
        '<div class="form-group" style="margin-bottom:0"><label style="font-size:0.6rem">A</label><input type="text" value="' + q.option_a + '" style="width:100%;padding:7px 10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:0.8125rem"></div>' +
        '<div class="form-group" style="margin-bottom:0"><label style="font-size:0.6rem">B</label><input type="text" value="' + q.option_b + '" style="width:100%;padding:7px 10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:0.8125rem"></div>' +
        '<div class="form-group" style="margin-bottom:0"><label style="font-size:0.6rem">C</label><input type="text" value="' + q.option_c + '" style="width:100%;padding:7px 10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:0.8125rem"></div>' +
        '<div class="form-group" style="margin-bottom:0"><label style="font-size:0.6rem">D</label><input type="text" value="' + q.option_d + '" style="width:100%;padding:7px 10px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:0.8125rem"></div>' +
        '</div>' +
        '<div class="grid-2" style="gap:10px">' +
        '<div class="form-group" style="margin-bottom:0"><label style="font-size:0.6rem">Correct</label><select style="width:100%;padding:7px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:0.8125rem"><option value="A"' + (q.correct_answer === 'A' ? ' selected' : '') + '>A</option><option value="B"' + (q.correct_answer === 'B' ? ' selected' : '') + '>B</option><option value="C"' + (q.correct_answer === 'C' ? ' selected' : '') + '>C</option><option value="D"' + (q.correct_answer === 'D' ? ' selected' : '') + '>D</option></select></div>' +
        '<div class="form-group" style="margin-bottom:0"><label style="font-size:0.6rem">Difficulty</label><select class="eq-diff" style="width:100%;padding:7px;border:1.5px solid var(--border);border-radius:var(--radius-sm);font-size:0.8125rem"><option value="Easy"' + (q.difficulty === 'Easy' ? ' selected' : '') + '>Easy</option><option value="Medium"' + (q.difficulty === 'Medium' ? ' selected' : '') + '>Medium</option><option value="Hard"' + (q.difficulty === 'Hard' ? ' selected' : '') + '>Hard</option></select></div>' +
        '</div>';
    container.appendChild(div);
}

function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
}

async function saveEditQuiz() {
    var quizId = document.getElementById('edit-quiz-id').value;
    var topic = document.getElementById('edit-topic').value.trim();
    var subject = document.getElementById('edit-subject').value.trim();
    var difficulty = document.getElementById('edit-difficulty').value;

    if (!topic) { document.getElementById('edit-feedback').innerHTML = '<div class="alert alert-warning">Topic is required.</div>'; return; }

    var questions = [];
    var cards = document.querySelectorAll('#edit-questions-container .card');
    if (cards.length === 0) { document.getElementById('edit-feedback').innerHTML = '<div class="alert alert-warning">Add at least one question.</div>'; return; }

    for (var i = 0; i < cards.length; i++) {
        var card = cards[i];
        var inputs = card.querySelectorAll('input, textarea, select');
        var diffs = card.querySelectorAll('.eq-diff');
        var q = {
            question_text: inputs[0].value.trim(),
            option_a: inputs[1].value.trim(),
            option_b: inputs[2].value.trim(),
            option_c: inputs[3].value.trim(),
            option_d: inputs[4].value.trim(),
            correct_answer: inputs[5].value,
            difficulty: diffs.length > 0 ? diffs[0].value : difficulty,
        };
        if (!q.question_text || !q.option_a || !q.option_b || !q.option_c || !q.option_d) {
            document.getElementById('edit-feedback').innerHTML = '<div class="alert alert-warning">Please fill all fields in Q' + (i + 1) + '.</div>';
            return;
        }
        questions.push(q);
    }

    var btn = document.querySelector('#edit-modal .btn-primary');
    btn.disabled = true; btn.textContent = 'Saving...';

    const result = await apiRequest('/api/mentor/quiz/' + quizId, 'PUT', { topic, subject, difficulty, questions });
    if (result.success) {
        document.getElementById('edit-feedback').innerHTML = '<div class="alert alert-success">Quiz updated successfully!</div>';
        setTimeout(function() { closeEditModal(); loadMentorQuizzes(); }, 800);
    } else {
        document.getElementById('edit-feedback').innerHTML = '<div class="alert alert-danger">' + (result.message || 'Failed to update') + '</div>';
        btn.disabled = false; btn.textContent = 'Save Changes';
    }
}

// ─── ACCESS CODE MANAGEMENT ──────────────────────────────────────────

async function loadAccessCodes() {
    const auth = await checkAuth();
    if (!auth || auth.role !== 'mentor') { window.location.href = '../login.html'; return; }

    const result = await apiRequest('/api/mentor/access-codes');
    if (!result.success) return;

    const container = document.getElementById('access-codes-container');
    if (!container) return;

    if (!result.data.length) {
        container.innerHTML = '<div class="card" style="text-align:center;padding:60px 40px"><div style="font-size:3rem;margin-bottom:12px">🔑</div><h2 style="margin-bottom:8px">No Access Codes Yet</h2><p style="color:var(--text-light);font-size:0.9rem;margin-bottom:20px">Publish a quiz to automatically generate Primary and Backup access codes.</p><a href="quizzes.html" class="btn btn-primary">Go to Quizzes</a></div>';
        return;
    }

    // Group codes by quiz_id
    var grouped = {};
    result.data.forEach(function(c) {
        if (!grouped[c.quiz_id]) {
            grouped[c.quiz_id] = { quiz: c, primary: null, backup: null };
        }
        if (c.type === 'primary') grouped[c.quiz_id].primary = c;
        else grouped[c.quiz_id].backup = c;
    });

    container.innerHTML = '<div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px"><h2 style="font-size:1.1rem;margin:0">All Quiz Access Codes</h2><span style="font-size:0.75rem;color:var(--neutral-400)">' + result.data.length + ' codes generated</span></div>';

    Object.keys(grouped).forEach(function(qid) {
        var g = grouped[qid];
        var q = g.quiz;
        var primary = g.primary;
        var backup = g.backup;

        var cardHtml = '<div class="ac-card">';
        cardHtml += '<div class="ac-card-header">';
        cardHtml += '<div><strong style="font-size:1rem">' + q.quiz_name + '</strong><div class="qi">' + (q.quiz_subject || 'General') + ' &middot; ' + (q.quiz_difficulty || 'N/A') + ' &middot; ' + (q.question_count || 0) + ' questions &middot; Created: ' + (q.created_date ? q.created_date.slice(0, 10) : '-') + '</div></div>';
        cardHtml += '</div>';

        cardHtml += '<div class="ac-two-codes">';

        // Primary Code Box
        cardHtml += '<div class="ac-code-box">';
        cardHtml += '<div class="lbl"><svg viewBox="0 0 24 24" fill="var(--blue-500)" style="width:10px;height:10px;vertical-align:middle;margin-right:6px"><circle cx="12" cy="12" r="12"/></svg>Primary Access Code</div>';
        if (primary) {
            var pStatus = primary.status;
            cardHtml += '<div class="code-row"><span class="ac-code">' + primary.code + '</span> <span class="ac-status ' + pStatus + '">' + (pStatus.charAt(0).toUpperCase() + pStatus.slice(1)) + '</span></div>';
            cardHtml += '<div class="info-row"><span>Uses: ' + (primary.used_count || 0) + '</span>';
            if (primary.start_date) cardHtml += '<span>Start: ' + primary.start_date + ' ' + (primary.start_time || '00:00') + '</span>';
            if (primary.expiry_date) cardHtml += '<span>Expiry: ' + primary.expiry_date + ' ' + (primary.expiry_time || '23:59') + '</span>';
            cardHtml += '</div>';
            if (primary.status === 'active') {
                cardHtml += '<div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">';
                cardHtml += '<button class="ac-copy-btn" onclick="copyCode(\'' + primary.code + '\')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>Copy</button>';
                cardHtml += '<button class="ac-copy-btn" onclick="openEditCodeModal(' + primary.code_id + ',' + q.quiz_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>Settings</button>';
                cardHtml += '<button class="ac-copy-btn" onclick="disableCode(' + primary.code_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>Disable</button>';
                cardHtml += '<button class="ac-copy-btn" onclick="expireCode(' + primary.code_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>Expire</button>';
                cardHtml += '</div>';
            }
        } else {
            cardHtml += '<div style="color:var(--neutral-400);font-size:0.8rem">Not generated</div>';
        }
        cardHtml += '</div>';

        // Backup Code Box
        cardHtml += '<div class="ac-code-box">';
        cardHtml += '<div class="lbl"><svg viewBox="0 0 24 24" fill="var(--amber-500)" style="width:10px;height:10px;vertical-align:middle;margin-right:6px"><circle cx="12" cy="12" r="12"/></svg>Backup / Recovery Code</div>';
        if (backup) {
            var bStatus = backup.status;
            cardHtml += '<div class="code-row"><span class="ac-code">' + backup.code + '</span> <span class="ac-status ' + bStatus + '">' + (bStatus.charAt(0).toUpperCase() + bStatus.slice(1)) + '</span></div>';
            cardHtml += '<div class="info-row"><span>Uses: ' + (backup.used_count || 0) + '</span>';
            if (backup.start_date) cardHtml += '<span>Start: ' + backup.start_date + ' ' + (backup.start_time || '00:00') + '</span>';
            if (backup.expiry_date) cardHtml += '<span>Expiry: ' + backup.expiry_date + ' ' + (backup.expiry_time || '23:59') + '</span>';
            cardHtml += '</div>';
            if (backup.status === 'active') {
                cardHtml += '<div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap">';
                cardHtml += '<button class="ac-copy-btn" onclick="copyCode(\'' + backup.code + '\')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>Copy</button>';
                cardHtml += '<button class="ac-copy-btn" onclick="openEditCodeModal(' + backup.code_id + ',' + q.quiz_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>Settings</button>';
                cardHtml += '<button class="ac-copy-btn" onclick="disableCode(' + backup.code_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>Disable</button>';
                cardHtml += '<button class="ac-copy-btn" onclick="expireCode(' + backup.code_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>Expire</button>';
                cardHtml += '</div>';
            }
        } else {
            cardHtml += '<div style="color:var(--neutral-400);font-size:0.8rem">Not generated</div>';
        }
        cardHtml += '</div>';

        cardHtml += '</div>'; // ac-two-codes

        // Bottom actions bar
        cardHtml += '<div class="ac-actions">';
        cardHtml += '<button class="ac-copy-btn" onclick="regenerateBackup(' + q.quiz_id + ')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>Regenerate Backup</button>';
        cardHtml += '<span style="font-size:0.7rem;color:var(--neutral-400);margin-left:auto">Created: ' + (q.created_date ? q.created_date.slice(0, 16) : '-') + '</span>';
        cardHtml += '</div>';

        cardHtml += '</div>';
        container.innerHTML += cardHtml;
    });
}

function copyCode(code) {
    var ta = document.createElement('textarea');
    ta.value = code;
    ta.style.position = 'fixed'; ta.style.left = '-9999px'; ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        showAlert('Copied: <code style="font-size:0.9rem;letter-spacing:.1em;padding:2px 8px;background:var(--brand-50);border-radius:4px;color:var(--brand-700)">' + code + '</code>', 'success');
    } catch (e) {
        navigator.clipboard.writeText(code).then(function() {
            showAlert('Copied: <code style="font-size:0.9rem;letter-spacing:.1em;padding:2px 8px;background:var(--brand-50);border-radius:4px;color:var(--brand-700)">' + code + '</code>', 'success');
        }).catch(function() {
            showAlert('Copy manually: ' + code, 'warning');
        });
    }
    document.body.removeChild(ta);
}

async function disableCode(codeId) {
    if (!confirm('Disable this access code? Students will not be able to use it.')) return;
    const result = await apiRequest('/api/mentor/access-code/' + codeId + '/disable', 'POST');
    if (result.success) { showAlert('Code disabled!', 'success'); loadAccessCodes(); }
    else { showAlert(result.message, 'danger'); }
}

async function expireCode(codeId) {
    if (!confirm('Expire this access code? It will be marked as expired immediately.')) return;
    const result = await apiRequest('/api/mentor/access-code/' + codeId + '/expire', 'POST');
    if (result.success) { showAlert('Code expired!', 'success'); loadAccessCodes(); }
    else { showAlert(result.message, 'danger'); }
}

async function regenerateBackup(quizId) {
    if (!confirm('Generate a new backup code for this quiz? The current backup will be disabled.')) return;
    const result = await apiRequest('/api/mentor/access-code/' + quizId + '/regenerate-backup', 'POST');
    if (result.success) {
        showAlert('New backup code: <code style="font-size:0.9rem;letter-spacing:.1em">' + result.backup_code + '</code>', 'success');
        loadAccessCodes();
    } else { showAlert(result.message, 'danger'); }
}

// ─── EDIT CODE SETTINGS MODAL ───────────────────────────────────────

function openEditCodeModal(codeId, quizId) {
    document.getElementById('edit-code-id').value = codeId;
    document.getElementById('edit-quiz-id').value = quizId || '';
    document.getElementById('edit-start-date').value = '';
    document.getElementById('edit-start-time').value = '';
    document.getElementById('edit-expiry-date').value = '';
    document.getElementById('edit-expiry-time').value = '';
    document.getElementById('edit-code-feedback').innerHTML = '';

    // Try to prefill from existing data
    var allCodes = document.querySelectorAll('.ac-card');
    document.getElementById('edit-code-modal').style.display = 'flex';
}

function closeEditCodeModal() {
    document.getElementById('edit-code-modal').style.display = 'none';
}

async function saveCodeSettings() {
    var codeId = document.getElementById('edit-code-id').value;
    var startDate = document.getElementById('edit-start-date').value;
    var startTime = document.getElementById('edit-start-time').value;
    var expiryDate = document.getElementById('edit-expiry-date').value;
    var expiryTime = document.getElementById('edit-expiry-time').value;

    var btn = document.querySelector('#edit-code-modal .btn-primary');
    btn.disabled = true; btn.textContent = 'Saving...';

    const result = await apiRequest('/api/mentor/access-code/' + codeId + '/update', 'PUT', {
        start_date: startDate || null,
        start_time: startTime || null,
        expiry_date: expiryDate || null,
        expiry_time: expiryTime || null,
    });

    btn.disabled = false; btn.textContent = 'Save Settings';
    if (result.success) {
        document.getElementById('edit-code-feedback').innerHTML = '<div class="alert alert-success">Settings updated! The code will now only work within the specified time window.</div>';
        setTimeout(function() { closeEditCodeModal(); loadAccessCodes(); }, 1200);
    } else {
        document.getElementById('edit-code-feedback').innerHTML = '<div class="alert alert-danger">' + (result.message || 'Failed to save') + '</div>';
    }
}

// ─── QUIZ REPORT PDF GENERATION ────────────────────────────────────

async function generateQuizReport(quizId) {
    var btn = event.target.closest('button');
    if (btn) { btn.disabled = true; btn.textContent = 'Loading...'; }

    try {
        console.log('[Report] Fetching report for quiz:', quizId);
        var result = await apiRequest('/api/mentor/quiz/' + quizId + '/report');
        console.log('[Report] API result:', result);

        if (btn) { btn.disabled = false; btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>Report'; }

        if (!result) {
            showAlert('No response from server. Restart the server and try again.', 'danger');
            return;
        }

        if (!result.success) {
            showAlert('Error: ' + (result.message || 'Failed to load report.'), 'danger');
            return;
        }

    var d = result.data;
    var quiz = d.quiz;
    var stats = d.stats;
    var results = d.results;

    var passColor = '#22c55e';
    var failColor = '#ef4444';
    var brandColor = '#4f46e5';

    var resultsHtml = '';
    if (results.length > 0) {
        resultsHtml = results.map(function(r, i) {
            var isPass = r.status === 'Pass';
            var statusColor = isPass ? passColor : failColor;
            var dateStr = r.date ? new Date(r.date).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) : '-';
            var timeMin = Math.floor(r.time_taken / 60);
            var timeSec = r.time_taken % 60;
            var timeStr = timeMin + 'm ' + timeSec + 's';
            return '<tr>' +
                '<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:0.8rem;color:#374155">' + (i + 1) + '</td>' +
                '<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:0.8rem;font-weight:600;color:#09090b">' + (r.student_name || 'Unknown') + '</td>' +
                '<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:0.75rem;color:#71717a">' + (r.student_code || '-') + '</td>' +
                '<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:0.8rem;text-align:center">' + r.marks + '/' + r.total_questions + '</td>' +
                '<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:0.8rem;text-align:center;font-weight:600;color:' + brandColor + '">' + r.accuracy + '%</td>' +
                '<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:0.8rem;text-align:center">' + timeStr + '</td>' +
                '<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;text-align:center"><span style="display:inline-block;padding:3px 10px;border-radius:999px;font-size:0.7rem;font-weight:600;color:#fff;background:' + statusColor + '">' + r.status + '</span></td>' +
                '<td style="padding:10px 12px;border-bottom:1px solid #e5e7eb;font-size:0.75rem;color:#a1a1aa">' + dateStr + '</td>' +
                '</tr>';
        }).join('');
    } else {
        resultsHtml = '<tr><td colspan="8" style="text-align:center;padding:40px;color:#a1a1aa;font-size:0.85rem">No students have attempted this quiz yet.</td></tr>';
    }

    var generatedDate = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });

    var reportHtml = '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Quiz Report - ' + quiz.topic + '</title>' +
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">' +
        '<style>' +
        '*{margin:0;padding:0;box-sizing:border-box}' +
        'body{font-family:Inter,-apple-system,sans-serif;background:#f8fafc;color:#18181b}' +
        '.report{max-width:900px;margin:40px auto;background:#fff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.04)}' +
        '.report-header{background:linear-gradient(135deg,' + brandColor + ',#3730a3);padding:40px 48px;color:#fff;position:relative;overflow:hidden}' +
        '.report-header::before{content:"";position:absolute;top:-50px;right:-50px;width:200px;height:200px;border-radius:50%;background:rgba(255,255,255,.08)}' +
        '.report-header::after{content:"";position:absolute;bottom:-30px;left:30%;width:120px;height:120px;border-radius:50%;background:rgba(255,255,255,.05)}' +
        '.report-logo{font-size:1.1rem;font-weight:700;margin-bottom:20px;letter-spacing:-.02em;position:relative;z-index:1}' +
        '.report-logo span{opacity:.7}' +
        '.report-title{font-size:1.8rem;font-weight:800;letter-spacing:-.03em;margin-bottom:6px;position:relative;z-index:1}' +
        '.report-subtitle{font-size:0.85rem;opacity:.8;font-weight:400;position:relative;z-index:1}' +
        '.report-meta{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:28px 48px;background:#fafafa;border-bottom:1px solid #e5e7eb}' +
        '.meta-item{text-align:center}' +
        '.meta-value{font-size:1.5rem;font-weight:700;color:' + brandColor + ';letter-spacing:-.02em}' +
        '.meta-label{font-size:0.65rem;color:#a1a1aa;font-weight:500;text-transform:uppercase;letter-spacing:.06em;margin-top:2px}' +
        '.report-section{padding:28px 48px}' +
        '.section-title{font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:.1em;color:#a1a1aa;margin-bottom:16px}' +
        '.info-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:8px}' +
        '.info-item{display:flex;align-items:center;gap:10px;padding:12px 16px;background:#f8fafc;border-radius:10px;border:1px solid #f0f0f0}' +
        '.info-icon{width:32px;height:32px;border-radius:8px;background:' + brandColor + ';display:flex;align-items:center;justify-content:center;flex-shrink:0}' +
        '.info-icon svg{width:16px;height:16px;color:#fff}' +
        '.info-text .lbl{font-size:0.6rem;color:#a1a1aa;font-weight:500;text-transform:uppercase;letter-spacing:.04em}' +
        '.info-text .val{font-size:0.85rem;font-weight:600;color:#09090b}' +
        '.stats-bar{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:20px}' +
        '.stat-pill{padding:16px 12px;border-radius:10px;text-align:center;border:1px solid #e5e7eb}' +
        '.stat-pill .num{font-size:1.2rem;font-weight:700;letter-spacing:-.02em}' +
        '.stat-pill .lbl{font-size:0.6rem;color:#a1a1aa;font-weight:500;text-transform:uppercase;letter-spacing:.04em;margin-top:2px}' +
        '.results-table{width:100%;border-collapse:collapse;margin-top:8px}' +
        '.results-table th{padding:10px 12px;text-align:left;font-size:0.65rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:#a1a1aa;border-bottom:2px solid #e5e7eb;background:#fafafa}' +
        '.results-table td{padding:10px 12px}' +
        '.report-footer{padding:24px 48px;border-top:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:center}' +
        '.footer-brand{font-size:0.75rem;color:#a1a1aa}' +
        '.footer-brand strong{color:#09090b}' +
        '.footer-date{font-size:0.7rem;color:#a1a1aa}' +
        '.print-btn{display:inline-flex;align-items:center;gap:6px;padding:10px 24px;border-radius:8px;border:none;cursor:pointer;font-size:0.8rem;font-weight:600;color:#fff;background:' + brandColor + ';transition:all .2s;margin:20px 48px 30px}' +
        '.print-btn:hover{background:#3730a3}' +
        '@media print{.print-btn{display:none}.report{border:none;box-shadow:none;margin:0}.report-header{print-color-adjust:exact;-webkit-print-color-adjust:exact}}' +
        '</style></head><body>' +
        '<div class="report">' +
        '<div class="report-header">' +
            '<div class="report-logo">AI<span>Learn</span> Quiz Report</div>' +
            '<div class="report-title">' + quiz.topic + '</div>' +
            '<div class="report-subtitle">' + (quiz.subject || 'General') + ' &middot; ' + quiz.difficulty + ' &middot; ' + stats.question_count + ' Questions</div>' +
        '</div>' +
        '<div class="report-meta">' +
            '<div class="meta-item"><div class="meta-value">' + stats.total_attempts + '</div><div class="meta-label">Total Attempts</div></div>' +
            '<div class="meta-item"><div class="meta-value" style="color:' + passColor + '">' + stats.passed + '</div><div class="meta-label">Passed</div></div>' +
            '<div class="meta-item"><div class="meta-value" style="color:' + failColor + '">' + stats.failed + '</div><div class="meta-label">Failed</div></div>' +
            '<div class="meta-item"><div class="meta-value">' + stats.pass_rate + '%</div><div class="meta-label">Pass Rate</div></div>' +
        '</div>' +
        '<div class="report-section">' +
            '<div class="section-title">Quiz Details</div>' +
            '<div class="info-grid">' +
                '<div class="info-item"><div class="info-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div><div class="info-text"><div class="lbl">Mentor</div><div class="val">' + d.mentor_name + '</div></div></div>' +
                '<div class="info-item"><div class="info-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg></div><div class="info-text"><div class="lbl">Access Code</div><div class="val" style="letter-spacing:.1em;font-family:monospace">' + d.unique_code + '</div></div></div>' +
                '<div class="info-item"><div class="info-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg></div><div class="info-text"><div class="lbl">Topic</div><div class="val">' + quiz.topic + '</div></div></div>' +
                '<div class="info-item"><div class="info-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg></div><div class="info-text"><div class="lbl">Avg Accuracy</div><div class="val">' + stats.avg_accuracy + '%</div></div></div>' +
            '</div>' +
            '<div class="stats-bar">' +
                '<div class="stat-pill" style="background:#f0fdf4;border-color:#bbf7d0"><div class="num" style="color:' + passColor + '">' + stats.passed + '</div><div class="lbl">Passed</div></div>' +
                '<div class="stat-pill" style="background:#fef2f2;border-color:#fecaca"><div class="num" style="color:' + failColor + '">' + stats.failed + '</div><div class="lbl">Failed</div></div>' +
                '<div class="stat-pill" style="background:#eef2ff;border-color:#c7d2fe"><div class="num" style="color:' + brandColor + '">' + stats.avg_accuracy + '%</div><div class="lbl">Avg Accuracy</div></div>' +
                '<div class="stat-pill" style="background:#fffbeb;border-color:#fde68a"><div class="num" style="color:#d97706">' + Math.floor(stats.avg_time / 60) + 'm</div><div class="lbl">Avg Time</div></div>' +
            '</div>' +
        '</div>' +
        '<div class="report-section" style="padding-top:0">' +
            '<div class="section-title">Student Results</div>' +
            '<table class="results-table">' +
                '<thead><tr>' +
                    '<th>#</th><th>Student Name</th><th>Code</th><th style="text-align:center">Score</th><th style="text-align:center">Accuracy</th><th style="text-align:center">Time</th><th style="text-align:center">Status</th><th>Date</th>' +
                '</tr></thead>' +
                '<tbody>' + resultsHtml + '</tbody>' +
            '</table>' +
        '</div>' +
        '<div class="report-footer">' +
            '<div class="footer-brand">Generated by <strong>AI Learn</strong> Platform</div>' +
            '<div class="footer-date">' + generatedDate + '</div>' +
        '</div>' +
        '</div>' +
        '<div style="text-align:center;padding:20px">' +
            '<button class="print-btn" onclick="window.print()"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg> Print / Save as PDF</button>' +
        '</div>' +
        '<script>window.onload=function(){window.print();}<\/script>' +
        '</body></html>';

    var reportWindow = window.open('', '_blank', 'width=1000,height=800');
    if (reportWindow) {
        reportWindow.document.write(reportHtml);
        reportWindow.document.close();
    } else {
        showAlert('Pop-up blocked. Please allow pop-ups and try again.', 'warning');
    }
    } catch (err) {
        console.error('Report generation error:', err);
        showAlert('Error generating report: ' + err.message, 'danger');
        if (btn) { btn.disabled = false; btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>Report'; }
    }
}
