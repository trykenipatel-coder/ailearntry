async function loadMentorDashboard() {
    const result = await apiRequest('/api/mentor/dashboard');
    if (!result.success) return;

    const d = result.data;
    document.getElementById('total-quizzes').textContent = d.total_quizzes;
    document.getElementById('total-students').textContent = d.total_students;
    document.getElementById('total-attempts').textContent = d.total_attempts;

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
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center">No data available.</td></tr>';
        return;
    }

    tbody.innerHTML = result.data.map(s => `
        <tr>
            <td>${s.name}</td>
            <td>${s.email}</td>
            <td>${s.quiz_count}</td>
            <td>${s.avg_accuracy || 0}%</td>
            <td>
                <span class="badge ${s.passed > 0 ? 'badge-success' : 'badge-danger'}">
                    ${s.passed || 0} / ${s.quiz_count || 0}
                </span>
            </td>
        </tr>
    `).join('');
}

async function loadAnalytics() {
    const result = await apiRequest('/api/mentor/analytics');
    if (!result.success) return;

    const d = result.data;

    // Topic performance
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
                </div>
            `;
        }).join('');
    }

    // Chart placeholder - show mini bar chart
    const chartContainer = document.getElementById('weekly-chart');
    if (chartContainer && d.weekly_stats.length) {
        const max = Math.max(...d.weekly_stats.map(w => w.attempts), 1);
        chartContainer.innerHTML = `
            <div style="display:flex;align-items:end;gap:12px;height:160px;padding:20px 0">
                ${d.weekly_stats.reverse().map(w => {
                    const height = (w.attempts / max) * 140;
                    return `
                        <div style="flex:1;text-align:center">
                            <div style="background:var(--primary-light);border-radius:4px;height:${height}px;margin:0 auto;width:100%;min-height:4px;transition:height 0.3s"></div>
                            <div style="font-size:0.7rem;margin-top:4px;color:var(--text-light)">${w.day ? w.day.slice(5) : ''}</div>
                            <div style="font-size:0.65rem;color:var(--text-light)">${w.avg_accuracy}%</div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
    }
}

// Create Manual Quiz
function addQuestion() {
    const container = document.getElementById('questions-container');
    const index = container.children.length;
    const div = document.createElement('div');
    div.className = 'card';
    div.style.marginBottom = '16px';
    div.innerHTML = `
        <div style="display:flex;justify-content:space-between;margin-bottom:12px">
            <strong>Question ${index + 1}</strong>
            <button type="button" class="btn btn-danger btn-sm" onclick="this.parentElement.parentElement.remove()">Remove</button>
        </div>
        <div class="form-group">
            <textarea name="q_text" placeholder="Enter question" required style="min-height:60px"></textarea>
        </div>
        <div class="grid-2">
            <div class="form-group">
                <label>Option A</label>
                <input type="text" name="q_a" placeholder="Option A" required>
            </div>
            <div class="form-group">
                <label>Option B</label>
                <input type="text" name="q_b" placeholder="Option B" required>
            </div>
            <div class="form-group">
                <label>Option C</label>
                <input type="text" name="q_c" placeholder="Option C" required>
            </div>
            <div class="form-group">
                <label>Option D</label>
                <input type="text" name="q_d" placeholder="Option D" required>
            </div>
        </div>
        <div class="form-group">
            <label>Correct Answer</label>
            <select name="q_correct">
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
                <option value="D">D</option>
            </select>
        </div>
    `;
    container.appendChild(div);
}

async function submitManualQuiz() {
    const topic = document.getElementById('quiz-topic').value.trim();
    const subject = document.getElementById('quiz-subject').value.trim();
    const difficulty = document.getElementById('quiz-difficulty').value;

    if (!topic) {
        showAlert('Please enter a quiz topic.', 'warning');
        return;
    }

    const questionCards = document.querySelectorAll('#questions-container .card');
    const questions = [];

    for (const card of questionCards) {
        const inputs = card.querySelectorAll('input, textarea, select');
        const q = {
            question_text: inputs[0].value.trim(),
            option_a: inputs[1].value.trim(),
            option_b: inputs[2].value.trim(),
            option_c: inputs[3].value.trim(),
            option_d: inputs[4].value.trim(),
            correct_answer: inputs[5].value,
        };
        if (!q.question_text || !q.option_a || !q.option_b || !q.option_c || !q.option_d) {
            showAlert('Please fill in all question fields.', 'warning');
            return;
        }
        questions.push(q);
    }

    if (questions.length === 0) {
        showAlert('Add at least one question.', 'warning');
        return;
    }

    const btn = document.querySelector('#manual-quiz-form button[type="button"]');
    btn.disabled = true;
    btn.textContent = 'Creating...';

    const result = await apiRequest('/api/mentor/create-quiz', 'POST', {
        topic, subject, difficulty, questions,
    });

    btn.disabled = false;
    btn.textContent = 'Create Quiz';

    if (result.success) {
        showAlert(result.message, 'success');
        setTimeout(() => window.location.reload(), 1000);
    } else {
        showAlert(result.message, 'danger');
    }
}

// AI Quiz Generation
async function generateAIQuiz() {
    const topic = document.getElementById('ai-topic').value.trim();
    const subject = document.getElementById('ai-subject').value.trim();
    const numQuestions = parseInt(document.getElementById('ai-num-questions').value) || 5;

    if (!topic) {
        showAlert('Please enter a topic for AI quiz generation.', 'warning');
        return;
    }

    const btn = document.querySelector('#ai-generate-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="width:18px;height:18px;border-width:2px;margin:0;display:inline-block;vertical-align:middle"></span> Generating...';

    const result = await apiRequest('/api/mentor/ai-generate-quiz', 'POST', {
        topic, subject, num_questions: numQuestions,
    });

    btn.disabled = false;
    btn.textContent = 'Generate with AI';

    const output = document.getElementById('ai-output');
    if (result.success) {
        output.innerHTML = `
            <div class="alert alert-success">${result.message}</div>
            <div class="card">
                <div class="card-header">Generated Questions Preview</div>
                ${result.questions.map((q, i) => `
                    <div style="padding:12px 0;border-bottom:1px solid var(--border)">
                        <p><strong>Q${i + 1}.</strong> ${q.question_text}</p>
                        <p style="font-size:0.85rem;color:var(--text-light)">
                            A: ${q.option_a} | B: ${q.option_b} | C: ${q.option_c} | D: ${q.option_d}
                            <br>Answer: ${q.correct_answer} | Difficulty: ${q.difficulty}
                            ${q.explanation ? `<br>Explanation: ${q.explanation}` : ''}
                        </p>
                    </div>
                `).join('')}
            </div>
        `;
    } else {
        output.innerHTML = `<div class="alert alert-danger">${result.message}</div>`;
    }
}
