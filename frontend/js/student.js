function escHtml(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Student Dashboard
async function loadStudentDashboard() {
    const auth = await checkAuth();
    if (!auth || auth.role !== 'student') { window.location.href = '../login.html'; return; }
    document.getElementById('userName').textContent = auth.name;

    const result = await apiRequest('/api/student/dashboard');
    if (!result.success) return;

    const d = result.data;
    document.getElementById('total-quizzes').textContent = d.total_quizzes;
    document.getElementById('avg-accuracy').textContent = d.avg_accuracy + '%';
    document.getElementById('passed').textContent = d.passed;
    document.getElementById('failed').textContent = d.failed;

    if (d.streak) {
        document.getElementById('streak-current').textContent = d.streak.current;
        document.getElementById('streak-longest').textContent = d.streak.longest;
    }

    const tbody = document.querySelector('#recent-results tbody');
    if (tbody && d.recent_results.length) {
        tbody.innerHTML = d.recent_results.map(r => {
            var certBtn = r.status === 'Pass'
                ? '<a href="scorecard.html?quiz_id=' + r.quiz_id + '" target="_blank" title="View Certificate" style="color:var(--brand-500);font-size:0.75rem;text-decoration:none;font-weight:500">Certificate</a>'
                : '';
            return '<tr>' +
                '<td>' + r.topic + '</td>' +
                '<td>' + r.marks + '/' + r.total_questions + '</td>' +
                '<td>' + r.accuracy + '%</td>' +
                '<td><span class="badge ' + (r.status === 'Pass' ? 'badge-success' : 'badge-danger') + '">' + r.status + '</span></td>' +
                '<td>' + r.date + '</td>' +
                '<td>' + certBtn + '</td>' +
                '</tr>';
        }).join('');
    }

    loadPrediction();
    loadBadges();
    loadFeedbacks();
    loadHeartbeat();
    loadMistakes();
    loadMomentum();
    loadStudentAnnouncements();
    loadConfidenceEstimator();
    loadRetentionDecay();
    loadCurriculumFlow();
    loadLeaderboard('dashboard-leaderboard');
}

async function loadPrediction() {
    const result = await apiRequest('/api/predict');
    if (!result.success) return;
    const p = result.prediction;
    const container = document.getElementById('prediction-container');
    if (!container) return;

    const trendClass = p.trend === 'improving' ? 'trend-improving' : p.trend === 'declining' ? 'trend-declining' : 'trend-stable';
    container.innerHTML = `
        <div class="grid-3">
            <div class="prediction-card">
                <div class="pred-label">Predicted Score</div>
                <div class="pred-value">${p.predicted_score || 'N/A'}%</div>
                <div class="pred-label">Next Quiz</div>
            </div>
            <div class="prediction-card">
                <div class="pred-label">Pass Probability</div>
                <div class="pred-value">${p.pass_probability || 'N/A'}%</div>
                <div class="pred-label">Based on History</div>
            </div>
            <div class="prediction-card">
                <div class="pred-label">Learning Speed</div>
                <div class="pred-value" style="font-size:1.8rem">${p.learning_speed || 'N/A'}</div>
                <div class="pred-label">Trend: <span class="${trendClass}">${p.trend}</span></div>
            </div>
        </div>
        ${result.knowledge_gaps && result.knowledge_gaps.length ? `
            <div class="card" style="margin-top:20px">
                <div class="card-header">Knowledge Gaps Detected</div>
                ${result.knowledge_gaps.map(g => `
                    <div class="alert alert-warning" style="margin-bottom:8px">
                        <strong>${g.topic}</strong> - Accuracy: ${g.accuracy}% (${g.fails} failures in ${g.attempts} attempts)
                    </div>
                `).join('')}
            </div>
        ` : ''}
    `;
}

// Available Quizzes
async function loadAvailableQuizzes() {
    const auth = await checkAuth();
    if (!auth || auth.role !== 'student') { window.location.href = '../login.html'; return; }

    const result = await apiRequest('/api/student/available-quizzes');
    if (!result.success) return;

    const container = document.getElementById('quizzes-container');
    if (!container) return;

    if (!result.data.length) {
        container.innerHTML = '<div class="alert alert-info">No quizzes available yet. Check back later!</div>';
        return;
    }

    container.innerHTML = result.data.map(q => `
        <div class="card">
            <div class="card-header">
                <span>${q.topic}</span>
                <span class="badge badge-primary">${q.difficulty}</span>
            </div>
            <p style="color:var(--text-light);margin-bottom:16px">Subject: ${q.subject || 'General'} | Created: ${q.created_date}</p>
            <a href="quiz.html?quiz_id=${q.quiz_id}" class="btn btn-primary">Start Quiz</a>
        </div>
    `).join('');
}

// Quiz State
let quizState = {
    quizId: null, questions: [], currentIndex: 0, answers: {},
    violations: 0, timer: null, seconds: 0, totalSeconds: 0, completed: false,
    accessCode: '', quizData: null,
};

// Check re-entry + show code entry on page load
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('code-entry-screen')) {
        checkQuizReEntry();
    }
});

async function checkQuizReEntry() {
    const quizId = getQueryParam('quiz_id');
    if (!quizId) {
        document.getElementById('code-entry-screen').innerHTML = '<div class="alert alert-danger">No quiz specified.</div>';
        return;
    }
    quizState.quizId = quizId;

    // Check if already completed (for UI message only)
    const result = await apiRequest(`/api/student/quiz/${quizId}/start`);
    if (result.already_completed) {
        // Show code entry screen with re-attempt message instead of blocking
        var hintEl = document.getElementById('re-entry-hint');
        if (hintEl) {
            hintEl.innerHTML = '<div class="alert alert-warning" style="text-align:left;font-size:0.8rem;margin-bottom:16px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px;flex-shrink:0"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> You\'ve already attempted this quiz. Enter a <strong>Backup Access Code</strong> (provided by your mentor) for another attempt.</div>';
            hintEl.style.display = 'block';
        }
        var inputEl = document.getElementById('access-code-input');
        if (inputEl) inputEl.placeholder = 'Enter BACKUP code for re-attempt';
        document.getElementById('already-completed-screen').classList.add('hidden');
        return;
    }
    if (!result.success) {
        document.getElementById('code-entry-screen').innerHTML =
            '<div class="alert alert-danger">' + (result.message || 'Quiz not available.') + '</div>';
        return;
    }

    // Store data from this single API call (avoids double call)
    quizState.quizData = result.data;
    quizState.quizTitle = result.data.quiz.topic;
    document.getElementById('quiz-title').textContent = quizState.quizTitle;
}

async function validateAndStart() {
    const codeInput = document.getElementById('access-code-input');
    const code = codeInput ? codeInput.value.trim().toUpperCase() : '';
    const errorEl = document.getElementById('code-error');
    const btn = document.getElementById('validate-code-btn');

    if (!code) {
        if (errorEl) { errorEl.classList.remove('hidden'); errorEl.textContent = 'Please enter an access code.'; }
        return;
    }

    btn.disabled = true;
    btn.textContent = 'Validating...';
    if (errorEl) errorEl.classList.add('hidden');

    const result = await apiRequest('/api/student/validate-code', 'POST', {
        code: code,
        quiz_id: parseInt(quizState.quizId),
    });

    btn.disabled = false;
    btn.textContent = 'Validate & Start';

    if (result.success) {
        quizState.accessCode = code;
        document.getElementById('code-entry-screen').classList.add('hidden');
        document.getElementById('start-screen').classList.remove('hidden');
        // Reload quiz data for re-attempt
        var reloadResult = await apiRequest('/api/student/quiz/' + quizState.quizId + '/start');
        if (reloadResult.success) {
            quizState.quizData = reloadResult.data;
            quizState.quizTitle = reloadResult.data.quiz.topic;
            document.getElementById('quiz-title').textContent = quizState.quizTitle;
        }
    } else {
        if (errorEl) {
            errorEl.classList.remove('hidden');
            errorEl.textContent = result.message || 'Invalid code. Please try again.';
        }
        if (result.already_completed) {
            var hintEl = document.getElementById('re-entry-hint');
            if (hintEl) {
                hintEl.innerHTML = '<div class="alert alert-warning" style="text-align:left;font-size:0.8rem;margin-bottom:16px"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px;flex-shrink:0"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> You\'ve already completed this quiz. Enter a <strong>Backup Access Code</strong> for another attempt.</div>';
                hintEl.style.display = 'block';
            }
        }
    }
}

async function startQuiz() {
    var data = quizState.quizData;
    if (!data) {
        showAlert('Quiz data not loaded. Please refresh.', 'danger');
        return;
    }

    quizState.questions = data.questions;
    quizState.totalSeconds = quizState.questions.length * 60;

    // Enter fullscreen mode for security
    if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(function(e) {
            console.warn('Fullscreen request failed:', e);
        });
    }

    document.getElementById('start-screen').classList.add('hidden');
    document.getElementById('quiz-screen').classList.remove('hidden');

    renderSecurityBar();
    setupMonitoring();
    startTimer();
    showQuestion();
}

function renderSecurityBar() {
    const bar = document.getElementById('security-bar');
    if (!bar) return;
    const items = [
        { label: 'Tab Focus', active: true, color: '#22c55e' },
        { label: 'Copy/Paste Blocked', active: true, color: '#22c55e' },
        { label: 'Right-Click Blocked', active: true, color: '#22c55e' },
        { label: 'Text Selection Disabled', active: true, color: '#22c55e' },
        { label: 'Print Screen Blocked', active: true, color: '#22c55e' },
        { label: 'DevTools Blocked', active: true, color: '#22c55e' },
        { label: 'Screenshot Detection', active: true, color: '#22c55e' },
        { label: 'Fullscreen Lock', active: true, color: '#22c55e' },
        { label: 'Time Tracking', active: true, color: '#22c55e' },
    ];
    bar.innerHTML = `
        <div class="security-bar-enhanced">
            <div class="sec-header">
                <div class="shield"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:24px;height:24px"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg></div>
                <h3>Browser Lockdown Mode Active</h3>
                <span class="live-badge">● LIVE</span>
            </div>
            <div class="sec-grid">
                ${items.map(i => `<div class="sec-item active"><span class="dot" style="background:${i.color};box-shadow:0 0 6px ${i.color}80"></span>${i.label}</div>`).join('')}
            </div>
        </div>`;
}

function speakQuestion(q) {
    if (!window.speechSynthesis) {
        showAlert('Text-to-speech not supported in this browser.', 'warning');
        return;
    }
    window.speechSynthesis.cancel();
    let text = q.text + '. ';
    const letters = ['A', 'B', 'C', 'D'];
    q.options.forEach((opt, i) => {
        text += `Option ${letters[i]}: ${opt}. `;
    });
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 0.85;
    utterance.pitch = 1;
    const voices = window.speechSynthesis.getVoices();
    const englishVoice = voices.find(v => v.lang.startsWith('en'));
    if (englishVoice) utterance.voice = englishVoice;
    window.speechSynthesis.speak(utterance);
}

function showQuestion() {
    const q = quizState.questions[quizState.currentIndex];
    if (!q) return finishQuiz();

    const total = quizState.questions.length;
    const progress = ((quizState.currentIndex + 1) / total) * 100;

    document.getElementById('progress-fill').style.width = progress + '%';
    document.getElementById('question-number').textContent = `Question ${quizState.currentIndex + 1} of ${total}`;
    document.getElementById('question-difficulty').textContent = q.difficulty;

    const qTextEl = document.getElementById('question-text');
    const safeIdx = quizState.currentIndex;
    qTextEl.innerHTML = `
        <span>${q.text}</span>
        <button onclick="event.stopPropagation();speakQuestion(quizState.questions[${safeIdx}])"
            style="display:inline-flex;align-items:center;gap:4px;margin-left:10px;padding:4px 10px;border:1.5px solid var(--border);border-radius:var(--radius-full);background:var(--surface);cursor:pointer;font-size:0.75rem;color:var(--brand-600);transition:all 0.2s;vertical-align:middle"
            onmouseover="this.style.borderColor='var(--brand-400)';this.style.background='var(--brand-50)'"
            onmouseout="this.style.borderColor='var(--border)';this.style.background='var(--surface)'"
            title="Listen to question with options">🔊 Listen</button>
    `;

    const letters = ['A', 'B', 'C', 'D'];
    document.getElementById('options-container').innerHTML = q.options.map((opt, i) => `
        <label class="option-item ${quizState.answers[q.id] === letters[i] ? 'selected' : ''}">
            <input type="radio" name="answer" value="${letters[i]}"
                ${quizState.answers[q.id] === letters[i] ? 'checked' : ''}
                onchange="selectAnswer(${q.id}, '${letters[i]}')">
            <span class="option-letter">${letters[i]}</span>
            <span>${opt}</span>
        </label>
    `).join('');

    document.getElementById('prev-btn').classList.toggle('hidden', quizState.currentIndex === 0);
    document.getElementById('next-btn').textContent = quizState.currentIndex === total - 1 ? 'Finish Quiz' : 'Next Question';
}

function selectAnswer(questionId, letter) { quizState.answers[questionId] = letter; }

function prevQuestion() {
    if (quizState.currentIndex > 0) { quizState.currentIndex--; showQuestion(); }
}

function nextQuestion() {
    const q = quizState.questions[quizState.currentIndex];
    if (!quizState.answers[q.id]) { showAlert('Please select an answer before continuing.', 'warning'); return; }
    if (quizState.currentIndex < quizState.questions.length - 1) {
        quizState.currentIndex++; showQuestion();
    } else { finishQuiz(); }
}

async function finishQuiz(terminated) {
    if (quizState.completed) return;
    quizState.completed = true;
    clearInterval(quizState.timer);
    // Exit fullscreen if active
    if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen();
    else if (document.webkitFullscreenElement && document.webkitExitFullscreen) document.webkitExitFullscreen();
    document.getElementById('quiz-screen').classList.add('hidden');
    document.getElementById('result-screen').classList.remove('hidden');
    document.getElementById('result-loading').classList.remove('hidden');

    const result = await apiRequest('/api/student/quiz/submit', 'POST', {
        quiz_id: parseInt(quizState.quizId),
        answers: quizState.answers,
        time_taken: quizState.seconds,
        access_code: quizState.accessCode,
    });

    document.getElementById('result-loading').classList.add('hidden');
    document.getElementById('result-content').classList.remove('hidden');

    if (result.success) {
        const s = result.summary;
        document.getElementById('score-display').textContent = s.accuracy + '%';
        document.getElementById('score-display').className = `score ${s.status === 'Pass' ? 'pass' : 'fail'}`;
        document.getElementById('status-text').textContent = s.status === 'Pass' ? 'Congratulations! You Passed!' : 'Better Luck Next Time!';
        document.getElementById('status-text').style.color = s.status === 'Pass' ? 'var(--success)' : 'var(--danger)';
    }

    // If terminated due to violations, show different message
    if (terminated) {
        var h2 = document.querySelector('#result-content h2');
        var p = document.querySelector('#result-content p');
        if (h2) h2.textContent = '🔒 Quiz Terminated';
        if (p) p.textContent = 'Your quiz was ended due to multiple security violations. Your responses have been submitted.';
        document.getElementById('score-display').style.display = 'none';
    }

    // Start auto-redirect countdown
    startRedirectCountdown();
}

function startRedirectCountdown() {
    var seconds = 5;
    var countdownEl = document.getElementById('redirect-countdown');
    var progressEl = document.getElementById('redirect-progress');
    if (countdownEl) countdownEl.textContent = seconds;

    var interval = setInterval(function() {
        seconds--;
        if (countdownEl) countdownEl.textContent = seconds;
        if (progressEl) {
            var pct = (seconds / 5) * 100;
            progressEl.style.width = pct + '%';
        }
        if (seconds <= 0) {
            clearInterval(interval);
            window.location.href = 'dashboard.html';
        }
    }, 1000);
}

function startTimer() {
    quizState.seconds = 0;
    quizState.timer = setInterval(() => {
        quizState.seconds++;
        const remaining = quizState.totalSeconds - quizState.seconds;
        document.getElementById('timer-display').textContent = formatTime(remaining);
        const el = document.getElementById('timer-display');
        if (remaining < 60) el.className = 'quiz-timer danger';
        else if (remaining < 180) el.className = 'quiz-timer warning';
        if (remaining <= 0) finishQuiz();
    }, 1000);
}

function formatTime(secs) {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// ─── ENHANCED SECURE MONITORING SYSTEM ────────────────────────────────
function setupMonitoring() {

    // ── 1. Tab / Window Focus ──
    document.addEventListener('visibilitychange', () => {
        if (document.hidden && !quizState.completed) handleViolation('tab_switch');
    });
    window.addEventListener('blur', () => {
        if (!quizState.completed) handleViolation('window_blur');
    });

    // ── Fullscreen exit = violation / auto-terminate ──
    document.addEventListener('fullscreenchange', function fsHandler() {
        if (!document.fullscreenElement && !quizState.completed) {
            handleViolation('fullscreen_exit');
        }
    });
    document.addEventListener('webkitfullscreenchange', function wfsHandler() {
        if (!document.webkitFullscreenElement && !quizState.completed) {
            handleViolation('fullscreen_exit');
        }
    });

    // ── 2. Right-Click ──
    document.addEventListener('contextmenu', (e) => {
        if (!quizState.completed) { e.preventDefault(); showInAppWarning('Right-click is disabled during quiz.', 'warning'); }
    });

    // ── 3. Copy / Paste / Cut ──
    document.addEventListener('copy', (e) => {
        if (!quizState.completed) { e.preventDefault(); showInAppWarning('Copying is disabled.', 'warning'); }
    });
    document.addEventListener('paste', (e) => {
        if (!quizState.completed) { e.preventDefault(); showInAppWarning('Pasting is disabled.', 'warning'); }
    });
    document.addEventListener('cut', (e) => {
        if (!quizState.completed) { e.preventDefault(); showInAppWarning('Cutting is disabled.', 'warning'); }
    });

    // ── 4. Text Selection ──
    document.addEventListener('selectstart', (e) => {
        if (!quizState.completed) { e.preventDefault(); }
    });

    // ── 5. Keyboard Shortcuts ──
    document.addEventListener('keydown', (e) => {
        if (quizState.completed) return;
        if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C' || e.key === 'v' || e.key === 'V')) {
            e.preventDefault(); return;
        }
        if (e.ctrlKey && e.shiftKey && (e.key === 'i' || e.key === 'I' || e.key === 'j' || e.key === 'J')) {
            e.preventDefault(); handleViolation('devtools'); return;
        }
        if (e.ctrlKey && e.shiftKey && (e.key === 'c' || e.key === 'C')) {
            e.preventDefault(); handleViolation('devtools'); return;
        }
        if (e.key === 'F12') { e.preventDefault(); handleViolation('devtools'); return; }
        if ((e.ctrlKey || e.metaKey) && (e.key === 'u' || e.key === 'U')) {
            e.preventDefault(); handleViolation('devtools'); return;
        }
        if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
            e.preventDefault(); return;
        }
        if ((e.ctrlKey || e.metaKey) && (e.key === 'p' || e.key === 'P')) {
            e.preventDefault(); handleViolation('print_screen'); return;
        }
        if (e.key === 'PrintScreen' || e.keyCode === 44) {
            e.preventDefault(); handleViolation('print_screen');
            showInAppWarning('Screenshot detected! This attempt has been logged.', 'danger');
            return;
        }
        if (e.altKey && (e.key === 'Tab' || e.key === 'F4')) {
            handleViolation('tab_switch'); return;
        }
    });

    // ── 6. Print Screen via keyup ──
    document.addEventListener('keyup', (e) => {
        if (quizState.completed) return;
        if (e.key === 'PrintScreen' || e.keyCode === 44) {
            e.preventDefault(); handleViolation('print_screen');
            showInAppWarning('Screenshot detected! This attempt has been logged.', 'danger');
        }
    });

    // ── 7. DevTools Detection via size check ──
    let devtoolsDetected = false;
    function checkDevTools() {
        if (quizState.completed) return;
        var threshold = 160;
        var widthDiff = window.outerWidth - window.innerWidth;
        var heightDiff = window.outerHeight - window.innerHeight;
        if (widthDiff > threshold || heightDiff > threshold) {
            if (!devtoolsDetected) {
                devtoolsDetected = true;
                handleViolation('devtools');
            }
        } else {
            devtoolsDetected = false;
        }
    }
    setInterval(checkDevTools, 1500);

    // ── 8. BeforeUnload ──
    window.addEventListener('beforeunload', (e) => {
        if (!quizState.completed) {
            e.preventDefault();
            e.returnValue = 'Quiz in progress! Your progress will be lost.';
        }
    });

    // ── 9. Window resize detection ──
    var lastWidth = window.innerWidth;
    var lastHeight = window.innerHeight;
    window.addEventListener('resize', function() {
        if (quizState.completed) return;
        var dw = Math.abs(window.innerWidth - lastWidth);
        var dh = Math.abs(window.innerHeight - lastHeight);
        if (dw > 300 || dh > 300) {
            handleViolation('window_blur');
        }
        lastWidth = window.innerWidth;
        lastHeight = window.innerHeight;
    });
}

function showInAppWarning(message, type = 'warning') {
    const existing = document.querySelector('.in-app-warning');
    if (existing) existing.remove();
    const div = document.createElement('div');
    div.className = `in-app-warning alert alert-${type}`;
    div.style.cssText = 'position:fixed;top:72px;right:16px;z-index:9999;max-width:320px;animation:slideIn 0.3s;box-shadow:0 4px 12px rgba(0,0,0,0.15)';
    div.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> ' + message;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 2000);
}

async function handleViolation(source = 'tab_switch') {
    if (quizState.completed) return;
    const result = await apiRequest('/api/monitor/violation', 'POST', {
        quiz_id: parseInt(quizState.quizId),
        source: source,
    });
    if (result.success) showViolationWarning(result.warning_count, result.terminated, source);
}

function showViolationWarning(count, terminated, source = 'tab_switch') {
    // Backend now terminates immediately on 1st violation
    clearInterval(quizState.timer);
    finishQuiz(true);
}

// Results
async function loadResults() {
    const auth = await checkAuth();
    if (!auth || auth.role !== 'student') { window.location.href = '../login.html'; return; }

    const result = await apiRequest('/api/student/results');
    if (!result.success) return;

    const tbody = document.querySelector('#results-table tbody');
    if (!tbody) return;
    if (!result.data.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center">No quiz results yet.</td></tr>';
        return;
    }
    tbody.innerHTML = result.data.map(r => {
        var scorecardBtn = r.status === 'Pass'
            ? '<a href="scorecard.html?quiz_id=' + r.quiz_id + '" target="_blank" class="btn btn-sm btn-primary" style="text-decoration:none;display:inline-flex;align-items:center;gap:4px;padding:4px 10px;font-size:0.7rem"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>Certificate</a>'
            : '<span style="color:var(--text-light);font-size:0.7rem">Failed</span>';
        return '<tr>' +
            '<td>' + r.topic + '</td>' +
            '<td>' + r.marks + '/' + r.total_questions + '</td>' +
            '<td>' + r.accuracy + '%</td>' +
            '<td><span class="badge ' + (r.difficulty === 'Easy' ? 'badge-success' : r.difficulty === 'Medium' ? 'badge-warning' : 'badge-danger') + '">' + r.difficulty + '</span></td>' +
            '<td><span class="badge ' + (r.status === 'Pass' ? 'badge-success' : 'badge-danger') + '">' + r.status + '</span></td>' +
            '<td>' + r.date + '</td>' +
            '<td>' + scorecardBtn + '</td>' +
            '</tr>';
    }).join('');
}

// Performance
async function loadPerformance() {
    const auth = await checkAuth();
    if (!auth || auth.role !== 'student') { window.location.href = '../login.html'; return; }

    const result = await apiRequest('/api/student/performance');
    if (!result.success) return;

    const container = document.getElementById('topic-analysis');
    if (!container) return;

    const d = result.data;
    if (d.topic_analysis.length) {
        container.innerHTML = d.topic_analysis.map(t => `
            <div class="card" style="margin-bottom:16px">
                <div class="card-header" style="margin-bottom:8px">
                    <span>${t.topic}</span>
                    <span class="badge ${t.avg_accuracy >= 60 ? 'badge-success' : t.avg_accuracy >= 40 ? 'badge-warning' : 'badge-danger'}">${t.avg_accuracy}% avg</span>
                </div>
                <p style="color:var(--text-light);font-size:0.9rem">Attempts: ${t.attempts} | Passed: ${t.passed} | Accuracy: ${t.avg_accuracy}%</p>
            </div>
        `).join('');
    } else {
        container.innerHTML = '<div class="alert alert-info">Complete some quizzes to see topic analysis.</div>';
    }

    loadRecommendations(d);
}

async function loadRecommendations(perfData) {
    const container = document.getElementById('recommendations');
    if (!container) return;

    const studentData = {
        averageScore: perfData.avg_accuracy || 0,
        topicsAnalyzed: (perfData.topic_analysis || []).map(t => ({
            topic: t.topic,
            accuracy: t.avg_accuracy,
            attempts: t.attempts,
        })),
        totalQuizzes: perfData.total_quizzes || 0,
    };

    const result = await apiRequest('/api/gemini/recommendations', 'POST', { studentData });
    if (!result.success || !result.data) {
        container.innerHTML = '<div class="alert alert-info">Complete more quizzes to get personalized learning recommendations.</div>';
        return;
    }

    const rec = result.data;
    let html = '';
    if (rec.strengths && rec.strengths.length) {
        html += '<div style="margin-bottom:12px"><strong style="color:var(--green-600)">✅ Strengths</strong><ul style="margin:4px 0 0 16px">' +
            rec.strengths.map(s => '<li style="color:var(--neutral-600);font-size:0.85rem">' + s + '</li>').join('') + '</ul></div>';
    }
    if (rec.improvementAreas && rec.improvementAreas.length) {
        html += '<div style="margin-bottom:12px"><strong style="color:var(--amber-600)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg> Areas for Improvement</strong><ul style="margin:4px 0 0 16px">' +
            rec.improvementAreas.map(s => '<li style="color:var(--neutral-600);font-size:0.85rem">' + s + '</li>').join('') + '</ul></div>';
    }
    if (rec.recommendations && rec.recommendations.length) {
        html += '<div style="margin-bottom:12px"><strong style="color:var(--blue-600)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg> Recommendations</strong><ul style="margin:4px 0 0 16px">' +
            rec.recommendations.map(s => '<li style="color:var(--neutral-600);font-size:0.85rem">' + s + '</li>').join('') + '</ul></div>';
    }
    if (rec.estimatedLearningSpeed) {
        html += '<div style="margin-top:12px;padding:8px 12px;background:var(--neutral-50);border-radius:var(--radius-sm);font-size:0.8rem;color:var(--neutral-500)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Learning Speed: <strong>' + rec.estimatedLearningSpeed + '</strong></div>';
    }
    container.innerHTML = html || '<div class="alert alert-info">Complete more quizzes to get personalized learning recommendations.</div>';
}

async function loadBadges() {
    const result = await apiRequest('/api/student/badges');
    if (!result.success) return;
    const container = document.getElementById('badges-container');
    if (!container) return;
    if (!result.data.length) {
        container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:20px 0">No badges yet. Keep learning and mentors will reward you!</div>';
        return;
    }
    container.innerHTML = '<div class="badges-grid">' + result.data.map(b =>
        '<div class="badge-item"><div class="bglow"></div><span class="bicon">' + (b.badge_icon || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:24px;height:24px"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/></svg>') + '</span><div class="bname">' + b.badge_name + '</div><div class="bfrom">by ' + (b.mentor_name || 'Mentor') + '</div></div>'
    ).join('') + '</div>';
}

async function loadFeedbacks() {
    const result = await apiRequest('/api/student/feedbacks');
    if (!result.success) return;
    const container = document.getElementById('feedbacks-container');
    if (!container) return;
    if (!result.data.length) {
        container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:20px 0">No feedback received yet.</div>';
        return;
    }
    container.innerHTML = result.data.map(f =>
        '<div class="feedback-item">' +
            '<div class="stars">' + '★'.repeat(f.rating) + '☆'.repeat(5 - f.rating) + '</div>' +
            (f.comment ? '<div class="fcomment">' + f.comment + '</div>' : '') +
            '<div class="fmeta">from <strong>' + f.mentor_name + '</strong> &middot; ' + f.created_at + '</div>' +
        '</div>'
    ).join('');
}

async function loadStudentAnnouncements() {
    const container = document.getElementById('student-announcements');
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

async function loadHeartbeat() {
    const container = document.getElementById('heartbeat-content');
    if (!container) return;
    const result = await apiRequest('/api/research/heartbeat');
    if (!result || !result.success) { container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">Could not load heartbeat data.</div>'; return; }
    const d = result.data;
    if (!d.best_time) {
        container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">' + d.message + '</div>';
        return;
    }
    container.innerHTML = '<div class="research-inner">' +
        '<div class="r-metric"><div class="r-val">' + d.best_time.label + '</div><div class="r-lbl">Best Study Time</div><div class="r-sub">' + d.best_time.avg_accuracy + '% avg accuracy</div></div>' +
        '<div class="r-metric"><div class="r-val">' + d.optimal_duration + 'm</div><div class="r-lbl">Optimal Duration</div><div class="r-sub">per session</div></div>' +
        (d.attention_decay ? '<div class="r-metric"><div class="r-val" style="color:var(--amber-600)">' + d.attention_decay + '%</div><div class="r-lbl">Attention Decay</div><div class="r-sub">first→second half</div></div>' : '') +
        '</div>';
}

async function loadMistakes() {
    const container = document.getElementById('mistake-content');
    if (!container) return;
    const result = await apiRequest('/api/research/mistakes');
    if (!result || !result.success) { container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">Could not load mistake data.</div>'; return; }
    const d = result.data;
    if (!d.dominant_pattern) {
        container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">' + d.message + '</div>';
        return;
    }
    const svgs = {
        careless:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:middle"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
        knowledge_gap:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:middle"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>',
        difficulty_mismatch:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:middle"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>'
    };
    container.innerHTML = '<div class="research-inner">' +
        '<div class="r-metric" style="grid-column:1/-1;border-bottom:1px solid var(--border-subtle);padding-bottom:12px;margin-bottom:8px">' +
            '<div style="font-size:1.5rem;margin-bottom:4px">' + (svgs[d.dominant_pattern.type] || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;vertical-align:middle"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12.01" y2="16"/><line x1="12" y1="8" x2="12" y2="12"/></svg>') + ' ' + d.dominant_pattern.label + '</div>' +
            '<div class="r-lbl" style="font-size:0.65rem">Dominant Pattern</div>' +
        '</div>' +
        Object.entries(d.type_counts || {}).map(function(e) {
            var lbls = {careless:'Careless', knowledge_gap:'Knowledge Gap', difficulty_mismatch:'Difficulty'};
            var ics = svgs;
            return '<div class="r-metric"><div class="r-val" style="font-size:1.1rem">' + (ics[e[0]] || '') + ' ' + e[1] + '</div><div class="r-lbl">' + (lbls[e[0]] || e[0]) + '</div></div>';
        }).join('') +
        '<div class="r-metric"><div class="r-val">' + d.total_errors + '</div><div class="r-lbl">Total Errors</div></div>' +
        '</div>';
}

async function loadMomentum() {
    const container = document.getElementById('momentum-content');
    if (!container) return;
    const result = await apiRequest('/api/research/momentum');
    if (!result || !result.success) { container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">Could not load momentum data.</div>'; return; }
    const d = result.data;
    if (!d.momentum_index && d.momentum_index !== 0) {
        container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">' + d.message + '</div>';
        return;
    }
    var qrisk = d.quit_risk || {};
    var riskColor = qrisk.label === 'High Risk' ? 'var(--red-500)' : qrisk.label === 'Medium Risk' ? 'var(--amber-500)' : 'var(--green-500)';
    var momColor = d.momentum_label === 'Strong Momentum' ? 'var(--green-500)' : d.momentum_label === 'Building Momentum' ? 'var(--blue-500)' : d.momentum_label === 'Stable' ? 'var(--amber-500)' : 'var(--red-500)';
    container.innerHTML = '<div class="research-inner">' +
        '<div class="r-metric"><div class="r-val" style="color:' + momColor + '">' + d.momentum_index + '</div><div class="r-lbl">Momentum Score</div><div class="r-sub">' + d.momentum_label + '</div></div>' +
        '<div class="r-metric"><div class="r-val"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;vertical-align:middle;margin-right:2px"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg> ' + d.current_streak + '</div><div class="r-lbl">Current Streak</div><div class="r-sub">Best: ' + d.longest_streak + ' days</div></div>' +
        '<div class="r-metric"><div class="r-val" style="color:' + riskColor + '">' + (qrisk.score || 0) + '%</div><div class="r-lbl">Quit Risk</div><div class="r-sub">' + (qrisk.label || 'N/A') + '</div></div>' +
        '</div>';
}

// 5 NEW RESEARCH FEATURES

async function loadConfidenceEstimator() {
    const c = document.getElementById('confidence-content'); if (!c) return;
    const r = await apiRequest('/api/research/confidence');
    if (!r || !r.success) { c.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">Could not load.</div>'; return; }
    const d = r.data;
    if (!d.gap_type || d.gap_type === 'INSUFFICIENT_DATA') { c.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">' + (d.message || 'Need more data') + '</div>'; return; }
    const icons = {OVERCONFIDENT:'⚡', ACCURATE:'✅', UNDERCONFIDENT:'📉'};
    const colors = {OVERCONFIDENT:'var(--amber-500)', ACCURATE:'var(--green-500)', UNDERCONFIDENT:'var(--blue-500)'};
    c.innerHTML = '<div class="research-inner">' +
        '<div class="r-metric"><div class="r-val" style="color:' + (colors[d.gap_type] || 'var(--neutral-600)') + '">' + (icons[d.gap_type] || '') + ' ' + d.label + '</div><div class="r-lbl">Self-Assessment</div></div>' +
        '<div class="r-metric"><div class="r-val">' + d.actual_avg + '%</div><div class="r-lbl">Actual Avg</div><div class="r-sub">vs ' + d.confidence_score + '% estimated</div></div>' +
        '<div class="r-metric" style="grid-column:1/-1"><div class="r-val" style="font-size:0.85rem;font-weight:500;color:' + (d.gap > 5 ? 'var(--amber-500)' : 'var(--green-500)') + '">Gap: ' + (d.gap > 0 ? '+' : '') + d.gap + '%</div><div class="r-lbl">Confidence Gap</div></div>' +
        '</div>';
}

async function loadRetentionDecay() {
    const c = document.getElementById('retention-content'); if (!c) return;
    const r = await apiRequest('/api/research/retention');
    if (!r || !r.success) { c.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">Could not load.</div>'; return; }
    const d = r.data;
    if (d.retention_pct === null || d.retention_pct === undefined) { c.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">' + d.message + '</div>'; return; }
    var retainColor = d.retention_pct >= 70 ? 'var(--green-500)' : d.retention_pct >= 40 ? 'var(--amber-500)' : 'var(--red-500)';
    c.innerHTML = '<div class="research-inner">' +
        '<div class="r-metric"><div class="r-val" style="color:' + retainColor + '">' + d.retention_pct + '%</div><div class="r-lbl">Knowledge Retention</div><div class="r-sub">Ebbinghaus Curve</div></div>' +
        '<div class="r-metric"><div class="r-val">' + d.days_since_last_study + 'd</div><div class="r-lbl">Last Study</div><div class="r-sub">' + d.days_until_forget + 'd until forget</div></div>' +
        (d.needs_review ? '<div class="r-metric" style="grid-column:1/-1"><div class="r-val" style="font-size:0.85rem;color:var(--red-500)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Review needed!</div><div class="r-lbl">Forgetting curve active</div></div>' : '') +
        '</div>';
}

async function loadCurriculumFlow() {
    const c = document.getElementById('curriculum-content'); if (!c) return;
    const r = await apiRequest('/api/research/curriculum');
    if (!r || !r.success) { c.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">Could not load.</div>'; return; }
    const d = r.data;
    if (!d.recommended_order && !d.topics) { c.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">No topics available.</div>'; return; }
    var items = d.recommended_order || d.topics || [];
    c.innerHTML = '<div class="research-inner" style="grid-template-columns:1fr">' +
        '<div class="r-metric"><div class="r-lbl" style="font-size:0.7rem;margin-bottom:6px">Recommended Learning Path</div>' +
        '<div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:center">' +
        items.map(function(t, i) {
            var arr = t.split(/[\s-]+/);
            var label = arr.length > 2 ? arr.map(function(w){return w[0]}).join('').toUpperCase() : t.length > 6 ? t.slice(0,6)+'…' : t;
            return '<span style="display:inline-flex;align-items:center;gap:4px;padding:5px 10px;border-radius:6px;background:var(--brand-50);color:var(--brand-700);font-size:0.7rem;font-weight:600">' +
                (i > 0 ? '<span style="color:var(--brand-300)">→</span>' : '') +
                label + '</span>';
        }).join('') +
        '</div></div></div>';
}

async function loadSpeedClustering() {
    const c = document.getElementById('clustering-content'); if (!c) return;
    const r = await apiRequest('/api/research/speed-clustering');
    if (!r || !r.success) { c.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">Could not load.</div>'; return; }
    const d = r.data;
    if (!d.type_distribution) { c.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:12px 0">' + (d.message || 'No data') + '</div>'; return; }
    var total = (d.type_distribution.FAST || 0) + (d.type_distribution.MEDIUM || 0) + (d.type_distribution.SLOW || 0);
    var colors = {FAST:'var(--green-500)', MEDIUM:'var(--amber-500)', SLOW:'var(--red-500)'};
    var labels = {FAST:'Fast Learners', MEDIUM:'Medium Learners', SLOW:'Slow Learners'};
    c.innerHTML = '<div class="research-inner">' +
        Object.entries(d.type_distribution).map(function(e) {
            var pct = total ? ((e[1] / total) * 100).toFixed(0) : 0;
            return '<div class="r-metric"><div class="r-val" style="font-size:1.1rem;color:' + (colors[e[0]] || 'var(--neutral-600)') + '">' + e[1] + '</div><div class="r-lbl">' + (labels[e[0]] || e[0]) + '</div><div class="r-sub">' + pct + '% of students</div></div>';
        }).join('') +
        '<div class="r-metric" style="grid-column:1/-1;padding-top:8px;border-top:1px solid var(--border-subtle)"><div class="r-lbl" style="font-size:0.65rem">K-Means Clustering (Unsupervised ML)</div></div>' +
        '</div>';
}

async function loadLeaderboard(containerId) {
    var container = document.getElementById(containerId);
    if (!container) return;
    try {
        var result = await apiRequest('/api/student/leaderboard');
        if (!result.success) { container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:40px 0">No data yet.</div>'; return; }
        var lb = result.data.leaderboard;
        var myRank = result.data.my_rank;
        if (!lb || !lb.length) {
            container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:40px 0">No data yet. Complete quizzes to see rankings.</div>';
            return;
        }
        var html = '<div style="max-height:296px;overflow-y:auto">';
        lb.slice(0, 5).forEach(function(s, i) {
            var medal = i === 0 ? '<svg viewBox="0 0 24 24" fill="#f59e0b" style="width:16px;height:16px"><circle cx="12" cy="12" r="10"/></svg>' : i === 1 ? '<svg viewBox="0 0 24 24" fill="#9ca3af" style="width:16px;height:16px"><circle cx="12" cy="12" r="10"/></svg>' : i === 2 ? '<svg viewBox="0 0 24 24" fill="#d97706" style="width:16px;height:16px"><circle cx="12" cy="12" r="10"/></svg>' : '<span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:var(--neutral-100);color:var(--neutral-500);font-size:0.65rem;font-weight:700">' + (i + 1) + '</span>';
            var isMe = myRank && s.student_id === myRank.student_id;
            var bg = isMe ? 'rgba(99,102,241,0.06)' : 'transparent';
            var border = isMe ? 'border-left:3px solid var(--brand-500)' : '';
            html += '<div style="display:flex;align-items:center;gap:10px;padding:7px 14px;border-bottom:1px solid var(--neutral-50);background:' + bg + ';' + border + '">';
            html += '<div style="flex-shrink:0">' + medal + '</div>';
            html += '<div style="flex:1;min-width:0">';
            html += '<div style="font-weight:600;font-size:0.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + escHtml(s.name) + (isMe ? ' <span style="color:var(--brand-500);font-size:0.6rem">(You)</span>' : '') + '</div>';
            html += '<div style="font-size:0.6rem;color:var(--text-light)">' + s.total_quizzes + ' quizzes</div>';
            html += '</div>';
            html += '<div style="font-weight:700;font-size:0.8rem;color:' + (s.avg_accuracy >= 70 ? 'var(--green-600)' : s.avg_accuracy >= 50 ? 'var(--amber-600)' : 'var(--red-500)') + '">' + s.avg_accuracy + '%</div>';
            html += '</div>';
        });
        if (lb.length > 5) {
            html += '<div style="text-align:center;padding:8px;font-size:0.7rem;color:var(--text-light)">+' + (lb.length - 5) + ' more</div>';
        }
        html += '</div>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<div style="color:var(--neutral-400);font-size:0.8rem;text-align:center;padding:40px 0">Could not load leaderboard</div>';
    }
}

async function loadStudentLeaderboard() {
    var container = document.getElementById('leaderboard-container');
    if (!container) return;

    try {
        var result = await apiRequest('/api/student/leaderboard');
        if (!result.success) { container.innerHTML = '<p style="color:var(--text-light);text-align:center;padding:40px">No data available</p>'; return; }

        var data = result.data;
        var lb = data.leaderboard;
        var myRank = data.my_rank;
        var stats = data.stats;

        // Update stat cards
        var myRankEl = document.getElementById('lb-my-rank');
        var myScoreEl = document.getElementById('lb-my-score');
        var topEl = document.getElementById('lb-top-score');
        var totalEl = document.getElementById('lb-total');
        if (myRankEl) myRankEl.textContent = myRank ? '#' + myRank.rank : '-';
        if (myScoreEl) myScoreEl.textContent = myRank ? myRank.avg_accuracy + '%' : '-';
        if (topEl) topEl.textContent = stats.top_score + '%';
        if (totalEl) totalEl.textContent = stats.total_students;

        // My rank card
        if (myRank) {
            var myCard = document.getElementById('my-rank-card');
            var myContent = document.getElementById('my-rank-content');
            if (myCard && myContent) {
                myCard.style.display = 'block';
                var html = '<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">';
                html += '<div style="font-size:2rem;font-weight:800;color:var(--brand-600)">#' + myRank.rank + '</div>';
                html += '<div style="flex:1;min-width:200px">';
                html += '<div style="font-weight:600;font-size:1rem">' + escHtml(myRank.name) + '</div>';
                html += '<div style="color:var(--text-light);font-size:0.8rem">' + escHtml(myRank.student_code || '') + '</div>';
                html += '</div>';
                html += '<div style="display:flex;gap:16px;text-align:center">';
                html += '<div><div style="font-size:1.2rem;font-weight:700;color:var(--brand-600)">' + myRank.avg_accuracy + '%</div><div style="font-size:0.65rem;color:var(--text-light)">Accuracy</div></div>';
                html += '<div><div style="font-size:1.2rem;font-weight:700;color:var(--green-600)">' + myRank.best_score + '%</div><div style="font-size:0.65rem;color:var(--text-light)">Best</div></div>';
                html += '<div><div style="font-size:1.2rem;font-weight:700">' + myRank.total_quizzes + '</div><div style="font-size:0.65rem;color:var(--text-light)">Quizzes</div></div>';
                html += '<div><div style="font-size:1.2rem;font-weight:700;color:var(--green-600)">' + myRank.passed + '</div><div style="font-size:0.65rem;color:var(--text-light)">Passed</div></div>';
                html += '</div>';

                // Goals to reach
                if (lb.length > 0) {
                    var nextRank = null;
                    for (var i = 0; i < lb.length; i++) {
                        if (lb[i].rank > myRank.rank) { nextRank = lb[i]; break; }
                    }
                    if (nextRank) {
                        var gap = (nextRank.avg_accuracy - myRank.avg_accuracy).toFixed(1);
                        html += '<div style="width:100%;margin-top:12px;padding:10px 14px;background:rgba(99,102,241,0.05);border-radius:6px;font-size:0.8rem">';
                        html += '<strong>To reach #' + nextRank.rank + ' (' + escHtml(nextRank.name) + '):</strong> Need <strong style="color:var(--brand-600)">+' + gap + '%</strong> more accuracy';
                        html += '</div>';
                    } else {
                        html += '<div style="width:100%;margin-top:12px;padding:10px 14px;background:rgba(34,197,94,0.05);border-radius:6px;font-size:0.8rem;color:var(--green-600)">';
                        html += '<strong>You are at the top! Keep it up!</strong>';
                        html += '</div>';
                    }
                }
                html += '</div>';
                myContent.innerHTML = html;
            }
        }

        // Full leaderboard
        if (!lb || lb.length === 0) {
            container.innerHTML = '<p style="color:var(--text-light);text-align:center;padding:40px">No student data yet</p>';
            return;
        }

        var html2 = '';
        html2 += '<div class="lb-row lb-header">';
        html2 += '<div>Rank</div>';
        html2 += '<div>Student</div>';
        html2 += '<div style="text-align:center">Accuracy</div>';
        html2 += '<div style="text-align:center">Quizzes</div>';
        html2 += '<div style="text-align:center">Best</div>';
        html2 += '<div style="text-align:center">Last</div>';
        html2 += '</div>';

        lb.forEach(function(s) {
            var rankClass = s.rank <= 3 ? 'rank-' + s.rank : 'rank-other';
            var rankIcon = s.rank === 1 ? '🥇' : s.rank === 2 ? '🥈' : s.rank === 3 ? '🥉' : s.rank;
            var isMe = myRank && s.student_id === myRank.student_id;
            var isTop3 = s.rank <= 3;

            html2 += '<div class="lb-row' + (isMe ? ' my-rank' : '') + '" style="' + (isTop3 && !isMe ? 'background:rgba(99,102,241,0.03)' : '') + '">';
            html2 += '<div><span class="rank-badge ' + rankClass + '">' + rankIcon + '</span></div>';
            html2 += '<div>';
            html2 += '<div style="font-weight:600;font-size:0.85rem">' + escHtml(s.name) + (isMe ? ' <span style="color:var(--brand-500);font-size:0.7rem">(You)</span>' : '') + '</div>';
            html2 += '<div style="font-size:0.7rem;color:var(--text-light)">' + escHtml(s.student_code || '') + '</div>';
            html2 += '</div>';
            html2 += '<div style="text-align:center">';
            html2 += '<span style="font-weight:700;color:' + (s.avg_accuracy >= 70 ? 'var(--green-600)' : s.avg_accuracy >= 50 ? 'var(--amber-600)' : 'var(--red-500)') + '">' + s.avg_accuracy + '%</span>';
            html2 += '</div>';
            html2 += '<div style="text-align:center;color:var(--text-light)">' + s.total_quizzes + '</div>';
            html2 += '<div style="text-align:center;color:var(--green-600);font-weight:500">' + s.best_score + '%</div>';
            html2 += '<div style="text-align:center;color:var(--text-light)">' + s.last_score + '%</div>';
            html2 += '</div>';
        });

        // Summary
        html2 += '<div style="padding:16px;background:var(--neutral-50);border-top:2px solid var(--neutral-100);display:flex;flex-wrap:wrap;gap:20px;font-size:0.8rem">';
        html2 += '<div>Total students: <strong>' + stats.total_students + '</strong></div>';
        html2 += '<div>Avg score: <strong>' + stats.avg_score + '%</strong></div>';
        html2 += '<div>Top: <strong style="color:var(--green-600)">' + escHtml(stats.top_name) + ' (' + stats.top_score + '%)</strong></div>';
        if (stats.my_improvement !== 0) {
            html2 += '<div style="margin-left:auto;color:' + (stats.my_improvement > 0 ? 'var(--green-600)' : 'var(--red-500)') + '">Your trend: <strong>' + (stats.my_improvement > 0 ? '+' : '') + stats.my_improvement + '%</strong></div>';
        }
        html2 += '</div>';

        container.innerHTML = html2;

    } catch (e) {
        container.innerHTML = '<p style="color:var(--text-light);text-align:center;padding:40px">Could not load leaderboard</p>';
    }
}

// Auto-load leaderboard if container exists on page
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('leaderboard-container')) {
        loadStudentLeaderboard();
    }
});
