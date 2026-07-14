// Student Dashboard
async function loadStudentDashboard() {
    const result = await apiRequest('/api/student/dashboard');
    if (!result.success) return;

    const d = result.data;
    document.getElementById('total-quizzes').textContent = d.total_quizzes;
    document.getElementById('avg-accuracy').textContent = d.avg_accuracy + '%';
    document.getElementById('passed').textContent = d.passed;
    document.getElementById('failed').textContent = d.failed;

    const tbody = document.querySelector('#recent-results tbody');
    if (tbody && d.recent_results.length) {
        tbody.innerHTML = d.recent_results.map(r => `
            <tr>
                <td>${r.topic}</td>
                <td>${r.marks}/${r.total_questions}</td>
                <td>${r.accuracy}%</td>
                <td><span class="badge ${r.status === 'Pass' ? 'badge-success' : 'badge-danger'}">${r.status}</span></td>
                <td>${r.date}</td>
            </tr>
        `).join('');
    }

    loadPrediction();
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
            <a href="/student/quiz?quiz_id=${q.quiz_id}" class="btn btn-primary">Start Quiz</a>
        </div>
    `).join('');
}

// Quiz Page
let quizState = {
    quizId: null,
    questions: [],
    currentIndex: 0,
    answers: {},
    violations: 0,
    timer: null,
    seconds: 0,
    totalSeconds: 0,
    completed: false,
};

async function startQuiz() {
    const params = new URLSearchParams(window.location.search);
    const quizId = params.get('quiz_id');
    if (!quizId) {
        document.getElementById('quiz-content').innerHTML = '<div class="alert alert-danger">No quiz specified.</div>';
        return;
    }

    const result = await apiRequest(`/api/student/quiz/${quizId}/start`);
    if (!result.success) {
        document.getElementById('quiz-content').innerHTML = `<div class="alert alert-danger">${result.message}</div>`;
        return;
    }

    quizState.quizId = quizId;
    quizState.questions = result.data.questions;
    quizState.totalSeconds = quizState.questions.length * 60;

    document.getElementById('quiz-title').textContent = result.data.quiz.topic;
    document.getElementById('start-screen').style.display = 'none';
    document.getElementById('quiz-screen').style.display = 'block';

    setupMonitoring();
    startTimer();
    showQuestion();
}

function showQuestion() {
    const q = quizState.questions[quizState.currentIndex];
    if (!q) return finishQuiz();

    const total = quizState.questions.length;
    const progress = ((quizState.currentIndex + 1) / total) * 100;

    document.getElementById('progress-fill').style.width = progress + '%';
    document.getElementById('question-number').textContent = `Question ${quizState.currentIndex + 1} of ${total}`;
    document.getElementById('question-difficulty').textContent = q.difficulty;
    document.getElementById('question-text').textContent = q.text;

    const letters = ['A', 'B', 'C', 'D'];
    const optionsHtml = q.options.map((opt, i) => `
        <label class="option-item ${quizState.answers[q.id] === letters[i] ? 'selected' : ''}">
            <input type="radio" name="answer" value="${letters[i]}"
                ${quizState.answers[q.id] === letters[i] ? 'checked' : ''}
                onchange="selectAnswer(${q.id}, '${letters[i]}')">
            <span class="option-letter">${letters[i]}</span>
            <span>${opt}</span>
        </label>
    `).join('');

    document.getElementById('options-container').innerHTML = optionsHtml;

    document.getElementById('prev-btn').style.display = quizState.currentIndex > 0 ? 'inline-flex' : 'none';
    document.getElementById('next-btn').textContent = quizState.currentIndex === total - 1 ? 'Finish Quiz' : 'Next Question';
}

function selectAnswer(questionId, letter) {
    quizState.answers[questionId] = letter;
}

function prevQuestion() {
    if (quizState.currentIndex > 0) {
        quizState.currentIndex--;
        showQuestion();
    }
}

function nextQuestion() {
    const q = quizState.questions[quizState.currentIndex];
    if (!quizState.answers[q.id]) {
        showAlert('Please select an answer before continuing.', 'warning');
        return;
    }

    if (quizState.currentIndex < quizState.questions.length - 1) {
        quizState.currentIndex++;
        showQuestion();
    } else {
        finishQuiz();
    }
}

async function finishQuiz() {
    if (quizState.completed) return;
    quizState.completed = true;

    clearInterval(quizState.timer);
    document.getElementById('quiz-screen').style.display = 'none';
    document.getElementById('result-screen').style.display = 'block';
    document.getElementById('result-loading').style.display = 'block';

    const result = await apiRequest('/api/student/quiz/submit', 'POST', {
        quiz_id: parseInt(quizState.quizId),
        answers: quizState.answers,
        time_taken: quizState.seconds,
    });

    document.getElementById('result-loading').style.display = 'none';
    document.getElementById('result-content').style.display = 'block';

    if (result.success) {
        const s = result.summary;
        document.getElementById('score-display').textContent = s.accuracy + '%';
        document.getElementById('score-display').className = `score ${s.status === 'Pass' ? 'pass' : 'fail'}`;
        document.getElementById('status-text').textContent = s.status === 'Pass' ? 'Congratulations! You Passed!' : 'Better Luck Next Time!';
        document.getElementById('status-text').style.color = s.status === 'Pass' ? 'var(--success)' : 'var(--danger)';
        document.getElementById('correct-count').textContent = `${s.correct}/${s.total}`;
        document.getElementById('accuracy-display').textContent = s.accuracy + '%';
        document.getElementById('time-display').textContent = formatTime(quizState.seconds);
    }
}

function startTimer() {
    quizState.seconds = 0;
    quizState.timer = setInterval(() => {
        quizState.seconds++;
        const remaining = quizState.totalSeconds - quizState.seconds;
        document.getElementById('timer-display').textContent = formatTime(remaining);

        const timer = document.getElementById('timer-display');
        if (remaining < 60) {
            timer.className = 'quiz-timer danger';
        } else if (remaining < 180) {
            timer.className = 'quiz-timer warning';
        }

        if (remaining <= 0) {
            finishQuiz();
        }
    }, 1000);
}

function formatTime(secs) {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// Monitoring
function setupMonitoring() {
    document.addEventListener('visibilitychange', () => {
        if (document.hidden && !quizState.completed) {
            handleViolation();
        }
    });

    window.addEventListener('blur', () => {
        if (!quizState.completed) {
            handleViolation();
        }
    });
}

async function handleViolation() {
    if (quizState.completed) return;

    const result = await apiRequest('/api/monitor/violation', 'POST', {
        quiz_id: parseInt(quizState.quizId),
    });

    if (result.success) {
        showViolationWarning(result.warning_count, result.terminated);
    }
}

function showViolationWarning(count, terminated) {
    const overlay = document.createElement('div');
    overlay.className = 'warning-overlay';

    if (terminated) {
        overlay.innerHTML = `
            <div class="warning-modal" id="terminated-modal">
                <div class="icon">&#128274;</div>
                <h2>Quiz Terminated</h2>
                <p>Multiple tab switches detected. Submitting your quiz...</p>
                <div class="spinner" style="width:24px;height:24px;margin:12px auto"></div>
            </div>
        `;
    } else {
        overlay.innerHTML = `
            <div class="warning-modal">
                <div class="icon">&#9888;</div>
                <h2>Warning! (${count}/2)</h2>
                <p>Tab switching is not allowed during the quiz. Another violation will terminate your quiz.</p>
                <button class="btn btn-warning" onclick="this.closest('.warning-overlay').remove()">I Understand</button>
            </div>
        `;
    }

    document.body.appendChild(overlay);
    if (terminated) {
        clearInterval(quizState.timer);
        finishQuiz().then(() => {
            const modal = document.getElementById('terminated-modal');
            if (modal) {
                modal.innerHTML = `
                    <div class="icon">&#128274;</div>
                    <h2>Quiz Terminated</h2>
                    <p>Your quiz has been submitted due to multiple tab switches.</p>
                    <button class="btn btn-danger" onclick="window.location.href='/student/dashboard'">Go to Dashboard</button>
                `;
            }
        });
    }
}

// Results Page
async function loadResults() {
    const result = await apiRequest('/api/student/results');
    if (!result.success) return;

    const tbody = document.querySelector('#results-table tbody');
    if (!tbody) return;

    if (!result.data.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">No quiz results yet.</td></tr>';
        return;
    }

    tbody.innerHTML = result.data.map(r => `
        <tr>
            <td>${r.topic}</td>
            <td>${r.marks}/${r.total_questions}</td>
            <td>${r.accuracy}%</td>
            <td><span class="badge ${r.difficulty === 'Easy' ? 'badge-success' : r.difficulty === 'Medium' ? 'badge-warning' : 'badge-danger'}">${r.difficulty}</span></td>
            <td><span class="badge ${r.status === 'Pass' ? 'badge-success' : 'badge-danger'}">${r.status}</span></td>
            <td>${r.date}</td>
        </tr>
    `).join('');
}

async function loadPerformance() {
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
                    <span class="badge ${t.avg_accuracy >= 60 ? 'badge-success' : t.avg_accuracy >= 40 ? 'badge-warning' : 'badge-danger'}">
                        ${t.avg_accuracy}% avg
                    </span>
                </div>
                <p style="color:var(--text-light);font-size:0.9rem">
                    Attempts: ${t.attempts} | Passed: ${t.passed} | Accuracy: ${t.avg_accuracy}%
                </p>
            </div>
        `).join('');
    } else {
        container.innerHTML = '<div class="alert alert-info">Complete some quizzes to see topic analysis.</div>';
    }
}
