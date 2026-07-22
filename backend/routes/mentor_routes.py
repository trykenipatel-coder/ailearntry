import os
from datetime import datetime
from flask import Blueprint, request, jsonify, session, send_from_directory
from database import get_db

mentor_bp = Blueprint("mentor", __name__)


@mentor_bp.route("/api/mentor/dashboard")
def dashboard():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    mentor_id = session["user_id"]

    total_quizzes = db.execute(
        "SELECT COUNT(*) FROM quizzes WHERE created_by = ? AND created_by_type = 'mentor'",
        (mentor_id,),
    ).fetchone()[0]

    total_students = db.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    total_attempts = db.execute(
        """SELECT COUNT(*) FROM quiz_results qr
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'""",
        (mentor_id,),
    ).fetchone()[0]

    recent_quizzes = db.execute(
        "SELECT * FROM quizzes WHERE created_by = ? AND created_by_type = 'mentor' ORDER BY created_date DESC LIMIT 5",
        (mentor_id,),
    ).fetchall()

    draft_count = db.execute(
        "SELECT COUNT(*) FROM quizzes WHERE created_by = ? AND status = 'draft'",
        (mentor_id,),
    ).fetchone()[0]

    total_materials = db.execute(
        "SELECT COUNT(*) FROM study_materials WHERE mentor_id = ?",
        (mentor_id,),
    ).fetchone()[0]

    recent_materials = db.execute(
        "SELECT * FROM study_materials WHERE mentor_id = ? ORDER BY created_date DESC LIMIT 5",
        (mentor_id,),
    ).fetchall()

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "total_quizzes": total_quizzes,
            "total_students": total_students,
            "total_attempts": total_attempts,
            "draft_count": draft_count,
            "total_materials": total_materials,
            "recent_quizzes": [dict(q) for q in recent_quizzes],
            "recent_materials": [dict(m) for m in recent_materials],
        },
    })


@mentor_bp.route("/api/mentor/create-quiz", methods=["POST"])
def create_quiz():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    topic = data.get("topic", "").strip()
    subject = data.get("subject", "").strip()
    difficulty = data.get("difficulty", "Easy")
    questions_data = data.get("questions", [])

    if not topic or not questions_data:
        return jsonify({"success": False, "message": "Topic and questions required"}), 400

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "INSERT INTO quizzes (topic, subject, difficulty, created_by, created_by_type, status) VALUES (?, ?, ?, ?, 'mentor', 'published')",
        (topic, subject, difficulty, session["user_id"]),
    )
    quiz_id = cursor.lastrowid

    for q in questions_data:
        cursor.execute(
            """INSERT INTO questions
               (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                quiz_id,
                q["question_text"],
                q["option_a"],
                q["option_b"],
                q["option_c"],
                q["option_d"],
                q["correct_answer"],
                q.get("difficulty", difficulty),
            ),
        )

    from database import generate_access_code
    primary_code = generate_access_code()
    backup_code = generate_access_code()
    cursor.execute(
        "INSERT INTO access_codes (quiz_id, code, type) VALUES (?, ?, 'primary')",
        (quiz_id, primary_code),
    )
    cursor.execute(
        "INSERT INTO access_codes (quiz_id, code, type) VALUES (?, ?, 'backup')",
        (quiz_id, backup_code),
    )

    db.commit()
    db.close()

    # Sync to Firebase
    try:
        from backend.services.firebase_service import create_quiz as fb_create, save_questions as fb_save
        fb_create(quiz_id, subject, topic, str(session["user_id"]), len(questions_data))
        fb_questions = [
            {"question_text": q["question_text"], "option_a": q["option_a"],
             "option_b": q["option_b"], "option_c": q["option_c"], "option_d": q["option_d"],
             "correct_answer": q["correct_answer"], "difficulty": q.get("difficulty", difficulty)}
            for q in questions_data
        ]
        fb_save(quiz_id, fb_questions)
    except Exception:
        pass

    return jsonify({"success": True, "message": "Quiz published and access codes generated!", "quiz_id": quiz_id, "primary_code": primary_code, "backup_code": backup_code})


@mentor_bp.route("/api/mentor/ai-generate-quiz", methods=["POST"])
def ai_generate_quiz():
    print("[AI Quiz] Route called, session role:", session.get("role"))
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        data = request.get_json()
        topic = data.get("topic", "").strip()
        subject = data.get("subject", "").strip()
        num_easy = int(data.get("num_easy", 0))
        num_medium = int(data.get("num_medium", 0))
        num_hard = int(data.get("num_hard", 0))

        print(f"[AI Quiz] Topic: {topic}, Easy: {num_easy}, Medium: {num_medium}, Hard: {num_hard}")

        if not topic:
            return jsonify({"success": False, "message": "Topic required"}), 400

        if num_easy + num_medium + num_hard == 0:
            num_easy, num_medium, num_hard = 2, 2, 1

        print("[AI Quiz] Importing gemini_service...")
        from backend.services.gemini_service import generate_quiz as gemini_quiz
        print("[AI Quiz] Calling generate_quiz...")
        questions = gemini_quiz(topic, subject, num_easy, num_medium, num_hard)
        print(f"[AI Quiz] Got {len(questions) if questions else 0} questions")

        if not questions:
            return jsonify({"success": False, "message": "Failed to generate quiz"}), 500

        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO quizzes (topic, subject, difficulty, created_by, created_by_type, status) VALUES (?, ?, 'Mixed', ?, 'mentor', 'published')",
            (topic, subject, session["user_id"]),
        )
        quiz_id = cursor.lastrowid

        for q in questions:
            qtext = q.get("question_text") or q.get("question", "")
            opt_a = q.get("option_a") or (q.get("options", ["", "", "", ""])[0] if len(q.get("options", [])) > 0 else "")
            opt_b = q.get("option_b") or (q.get("options", ["", "", "", ""])[1] if len(q.get("options", [])) > 1 else "")
            opt_c = q.get("option_c") or (q.get("options", ["", "", "", ""])[2] if len(q.get("options", [])) > 2 else "")
            opt_d = q.get("option_d") or (q.get("options", ["", "", "", ""])[3] if len(q.get("options", [])) > 3 else "")
            answer = q.get("correct_answer") or q.get("correctAnswer", "")
            difficulty = q.get("difficulty", "Easy")
            explanation = q.get("explanation", "")

            cursor.execute(
                """INSERT INTO questions
                   (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty, explanation)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (quiz_id, qtext, opt_a, opt_b, opt_c, opt_d, answer, difficulty, explanation),
            )

        from database import generate_access_code
        primary_code = generate_access_code()
        backup_code = generate_access_code()
        cursor.execute(
            "INSERT INTO access_codes (quiz_id, code, type) VALUES (?, ?, 'primary')",
            (quiz_id, primary_code),
        )
        cursor.execute(
            "INSERT INTO access_codes (quiz_id, code, type) VALUES (?, ?, 'backup')",
            (quiz_id, backup_code),
        )

        db.commit()
        db.close()

        try:
            from backend.services.firebase_service import save_questions as fb_save, create_quiz as fb_create
            fb_create(quiz_id, subject, topic, session["user_id"], len(questions))
            fb_save(quiz_id, questions)
        except Exception:
            pass

        return jsonify({
            "success": True,
            "message": f"Quiz published! {len(questions)} questions ready.",
            "quiz_id": quiz_id,
            "primary_code": primary_code,
            "backup_code": backup_code,
            "questions": questions,
        })

    except Exception as e:
        print(f"[AI Quiz] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Quiz generation error: {str(e)}"}), 500


@mentor_bp.route("/api/mentor/publish-quiz/<int:quiz_id>", methods=["POST"])
def publish_quiz(quiz_id):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    db.execute("UPDATE quizzes SET status = 'published' WHERE quiz_id = ? AND created_by = ?",
               (quiz_id, session["user_id"]))
    # Disable any existing active codes for this quiz
    db.execute(
        "UPDATE access_codes SET status = 'disabled' WHERE quiz_id = ? AND status = 'active'",
        (quiz_id,),
    )
    # Auto-generate Primary and Backup access codes
    from database import generate_access_code
    primary_code = generate_access_code()
    backup_code = generate_access_code()
    db.execute(
        "INSERT INTO access_codes (quiz_id, code, type) VALUES (?, ?, 'primary')",
        (quiz_id, primary_code),
    )
    db.execute(
        "INSERT INTO access_codes (quiz_id, code, type) VALUES (?, ?, 'backup')",
        (quiz_id, backup_code),
    )
    db.commit()
    db.close()
    return jsonify({
        "success": True,
        "message": "Quiz published!",
        "quiz_id": quiz_id,
        "primary_code": primary_code,
        "backup_code": backup_code,
    })


@mentor_bp.route("/api/mentor/my-drafts")
def my_drafts():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    drafts = db.execute(
        "SELECT * FROM quizzes WHERE created_by = ? AND status = 'draft' ORDER BY created_date DESC",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(d) for d in drafts]})


def generate_fallback_quiz(topic, num_questions):
    templates = {
        "general": [
            {
                "question_text": f"What is the primary concept of {topic}?",
                "option_a": "Definition A", "option_b": "Definition B",
                "option_c": "Definition C", "option_d": "Definition D",
                "correct_answer": "A", "difficulty": "Easy",
                "explanation": f"This is the basic definition of {topic}.",
            },
            {
                "question_text": f"Which of the following best describes {topic}?",
                "option_a": "Description 1", "option_b": "Description 2",
                "option_c": "Description 3", "option_d": "Description 4",
                "correct_answer": "B", "difficulty": "Easy",
                "explanation": f"The correct description relates to key aspects of {topic}.",
            },
            {
                "question_text": f"What is a key application of {topic} in real-world scenarios?",
                "option_a": "Application X", "option_b": "Application Y",
                "option_c": "Application Z", "option_d": "Application W",
                "correct_answer": "C", "difficulty": "Medium",
                "explanation": f"{topic} has many practical applications including this one.",
            },
            {
                "question_text": f"Which historical figure is most associated with {topic}?",
                "option_a": "Person A", "option_b": "Person B",
                "option_c": "Person C", "option_d": "Person D",
                "correct_answer": "A", "difficulty": "Medium",
                "explanation": f"This person made significant contributions to {topic}.",
            },
            {
                "question_text": f"What is the most advanced current research direction in {topic}?",
                "option_a": "Research A", "option_b": "Research B",
                "option_c": "Research C", "option_d": "Research D",
                "correct_answer": "D", "difficulty": "Hard",
                "explanation": f"Cutting-edge research in {topic} focuses on this area.",
            },
        ]
    }

    if topic.lower() in ["digestive system", "human digestive system", "digestion"]:
        templates["general"] = [
            {
                "question_text": "What is the primary function of the digestive system?",
                "option_a": "To pump blood", "option_b": "To break down food and absorb nutrients",
                "option_c": "To produce hormones", "option_d": "To filter waste from blood",
                "correct_answer": "B", "difficulty": "Easy",
                "explanation": "The digestive system breaks down food into nutrients that the body can absorb.",
            },
            {
                "question_text": "Which organ is responsible for bile production?",
                "option_a": "Stomach", "option_b": "Pancreas",
                "option_c": "Liver", "option_d": "Small intestine",
                "correct_answer": "C", "difficulty": "Easy",
                "explanation": "The liver produces bile, which helps digest fats.",
            },
            {
                "question_text": "Where does most nutrient absorption occur?",
                "option_a": "Large intestine", "option_b": "Stomach",
                "option_c": "Small intestine", "option_d": "Mouth",
                "correct_answer": "C", "difficulty": "Medium",
                "explanation": "The small intestine is the primary site for nutrient absorption.",
            },
            {
                "question_text": "What is the role of hydrochloric acid in the stomach?",
                "option_a": "Neutralize toxins", "option_b": "Kill bacteria and activate enzymes",
                "option_c": "Absorb vitamins", "option_d": "Produce mucus",
                "correct_answer": "B", "difficulty": "Medium",
                "explanation": "HCl creates an acidic environment that kills bacteria and activates pepsin.",
            },
            {
                "question_text": "Which enzyme breaks down starch in the mouth?",
                "option_a": "Pepsin", "option_b": "Amylase",
                "option_c": "Lipase", "option_d": "Trypsin",
                "correct_answer": "B", "difficulty": "Hard",
                "explanation": "Salivary amylase begins the digestion of starch in the mouth.",
            },
        ]

    questions = templates["general"][:num_questions]
    while len(questions) < num_questions:
        questions.append(questions[-1])

    return questions


@mentor_bp.route("/api/mentor/student-performance")
def student_performance():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    data = db.execute(
        """SELECT s.student_id, s.name, s.email, s.student_code,
                  COUNT(qr.result_id) as quiz_count,
                  ROUND(AVG(qr.accuracy), 2) as avg_accuracy,
                  SUM(CASE WHEN qr.status='Pass' THEN 1 ELSE 0 END) as passed
           FROM students s
           LEFT JOIN quiz_results qr ON s.student_id = qr.student_id
           GROUP BY s.student_id ORDER BY avg_accuracy DESC"""
    ).fetchall()
    db.close()

    return jsonify({
        "success": True,
        "data": [dict(d) for d in data],
    })


@mentor_bp.route("/api/mentor/analytics")
def analytics():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    mentor_id = session["user_id"]

    topic_performance = db.execute(
        """SELECT q.topic, COUNT(qr.result_id) as attempts,
                  ROUND(AVG(qr.accuracy), 2) as avg_accuracy
           FROM quizzes q JOIN quiz_results qr ON q.quiz_id = qr.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           GROUP BY q.topic""",
        (mentor_id,),
    ).fetchall()

    weekly_stats = db.execute(
        """SELECT DATE(qr.date) as day, COUNT(*) as attempts,
                  ROUND(AVG(qr.accuracy), 2) as avg_accuracy
           FROM quiz_results qr JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           GROUP BY DATE(qr.date) ORDER BY day DESC LIMIT 7""",
        (mentor_id,),
    ).fetchall()

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "topic_performance": [dict(t) for t in topic_performance],
            "weekly_stats": [dict(w) for w in weekly_stats],
        },
    })


@mentor_bp.route("/api/mentor/student-heatmap")
def student_heatmap():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    mentor_id = session["user_id"]

    # Get study times grouped by hour for all students under this mentor
    hourly_data = db.execute(
        """SELECT CAST(strftime('%H', qr.date) AS INTEGER) as hour,
                  COUNT(*) as attempts,
                  ROUND(AVG(qr.accuracy), 1) as avg_accuracy
           FROM quiz_results qr
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           GROUP BY hour ORDER BY hour""",
        (mentor_id,),
    ).fetchall()

    # Get day-of-week distribution
    daily_data = db.execute(
        """SELECT CAST(strftime('%w', qr.date) AS INTEGER) as day_num,
                  COUNT(*) as attempts,
                  ROUND(AVG(qr.accuracy), 1) as avg_accuracy
           FROM quiz_results qr
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           GROUP BY day_num ORDER BY day_num""",
        (mentor_id,),
    ).fetchall()

    # Get student activity ranking
    student_activity = db.execute(
        """SELECT s.name, s.student_code, COUNT(qr.result_id) as total_attempts,
                  ROUND(AVG(qr.accuracy), 1) as avg_accuracy,
                  MAX(qr.date) as last_active
           FROM quiz_results qr
           JOIN students s ON qr.student_id = s.student_id
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           GROUP BY s.student_id ORDER BY total_attempts DESC LIMIT 10""",
        (mentor_id,),
    ).fetchall()

    db.close()

    # Build heatmap: 24 hours x 7 days
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    heatmap_grid = {}
    for d in daily_data:
        for h in range(24):
            key = f"{d['day_num']}_{h}"
            heatmap_grid[key] = {"attempts": 0, "accuracy": 0}

    for h in hourly_data:
        hour = h["hour"]
        # Distribute hourly totals across days proportionally
        day_count = len(daily_data) if daily_data else 1
        for d in daily_data:
            key = f"{d['day_num']}_{hour}"
            if key not in heatmap_grid:
                heatmap_grid[key] = {"attempts": 0, "accuracy": 0}
            # Weight by day's proportion
            heatmap_grid[key]["attempts"] = max(0, int(h["attempts"] / day_count))
            heatmap_grid[key]["accuracy"] = h["avg_accuracy"]

    return jsonify({
        "success": True,
        "data": {
            "hourly": [dict(h) for h in hourly_data],
            "daily": [dict(d) for d in daily_data],
            "day_names": day_names,
            "student_activity": [dict(s) for s in student_activity],
            "heatmap_grid": heatmap_grid,
        },
    })


@mentor_bp.route("/api/mentor/live-activity")
def live_activity():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    mentor_id = session["user_id"]

    # Active (flagged/cheating): students who have violations — caught during quiz
    active_students = db.execute(
        """SELECT DISTINCT s.name, s.student_code, q.topic,
                  MAX(v.date) as last_activity,
                  COUNT(v.warning_count) as warning_count
           FROM violations v
           JOIN students s ON v.student_id = s.student_id
           JOIN quizzes q ON v.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           GROUP BY s.student_id
           ORDER BY last_activity DESC""",
        (mentor_id,),
    ).fetchall()

    # Just finished: 10 most recent quiz completions
    just_finished = db.execute(
        """SELECT s.name, s.student_code, q.topic, qr.accuracy, qr.date, qr.status
           FROM quiz_results qr
           JOIN students s ON qr.student_id = s.student_id
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           ORDER BY qr.date DESC LIMIT 10""",
        (mentor_id,),
    ).fetchall()

    # In progress: students who took long (>300s) — still working on it
    recent_starts = db.execute(
        """SELECT s.name, s.student_code, q.topic, qr.accuracy, qr.time_taken, qr.date
           FROM quiz_results qr
           JOIN students s ON qr.student_id = s.student_id
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
             AND qr.time_taken > 300
           ORDER BY qr.date DESC LIMIT 10""",
        (mentor_id,),
    ).fetchall()

    # Activity log: latest 15 events (finished + violations mixed)
    recent_activity = db.execute(
        """SELECT s.name, s.student_code, q.topic, qr.accuracy, qr.date,
                  'finished' as action, qr.status
           FROM quiz_results qr
           JOIN students s ON qr.student_id = s.student_id
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           UNION ALL
           SELECT s.name, s.student_code, q.topic, NULL, v.date,
                  v.source as action, NULL
           FROM violations v
           JOIN students s ON v.student_id = s.student_id
           JOIN quizzes q ON v.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           ORDER BY date DESC LIMIT 15""",
        (mentor_id, mentor_id),
    ).fetchall()

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "active_count": len(active_students),
            "finished_count": len(just_finished),
            "started_count": len(recent_starts),
            "active_students": [dict(s) for s in active_students],
            "just_finished": [dict(s) for s in just_finished],
            "recent_starts": [dict(s) for s in recent_starts],
            "activity_log": [dict(a) for a in recent_activity],
        },
    })


@mentor_bp.route("/api/mentor/student-trend/<int:student_id>")
def student_trend(student_id):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    mentor_id = session["user_id"]

    # Verify student belongs to this mentor's quizzes
    check = db.execute(
        """SELECT 1 FROM quiz_results qr
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE qr.student_id = ? AND q.created_by = ? AND q.created_by_type = 'mentor'
           LIMIT 1""",
        (student_id, mentor_id),
    ).fetchone()

    if not check:
        db.close()
        return jsonify({"success": False, "message": "Student not found"}), 404

    # Get student info
    student = db.execute(
        "SELECT name, student_code, course FROM students WHERE student_id = ?",
        (student_id,),
    ).fetchone()

    # Get quiz results over time
    results = db.execute(
        """SELECT qr.date, qr.marks, qr.total_questions, qr.accuracy,
                  qr.topic, qr.difficulty, qr.time_taken, qr.status
           FROM quiz_results qr
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE qr.student_id = ? AND q.created_by = ? AND q.created_by_type = 'mentor'
           ORDER BY qr.date ASC""",
        (student_id, mentor_id),
    ).fetchall()

    # Calculate trend insights
    scores = [r["accuracy"] for r in results]
    trend_direction = "stable"
    improvement = 0
    if len(scores) >= 2:
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]
        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0
        improvement = round(avg_second - avg_first, 1)
        if improvement > 5:
            trend_direction = "improving"
        elif improvement < -5:
            trend_direction = "declining"

    # Best and worst topics
    topic_scores = {}
    for r in results:
        t = r["topic"]
        if t not in topic_scores:
            topic_scores[t] = []
        topic_scores[t].append(r["accuracy"])

    topic_avg = {t: round(sum(v)/len(v), 1) for t, v in topic_scores.items()}
    best_topic = max(topic_avg, key=topic_avg.get) if topic_avg else "N/A"
    worst_topic = min(topic_avg, key=topic_avg.get) if topic_avg else "N/A"

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "student": dict(student),
            "results": [dict(r) for r in results],
            "insights": {
                "total_quizzes": len(results),
                "avg_score": round(sum(scores)/len(scores), 1) if scores else 0,
                "best_score": max(scores) if scores else 0,
                "worst_score": min(scores) if scores else 0,
                "trend_direction": trend_direction,
                "improvement": improvement,
                "best_topic": best_topic,
                "worst_topic": worst_topic,
                "topic_averages": topic_avg,
            },
        },
    })


@mentor_bp.route("/api/mentor/compare-students", methods=["POST"])
def compare_students():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    student_a_id = data.get("student_a")
    student_b_id = data.get("student_b")

    if not student_a_id or not student_b_id:
        return jsonify({"success": False, "message": "Both student IDs required"}), 400
    if student_a_id == student_b_id:
        return jsonify({"success": False, "message": "Select two different students"}), 400

    db = get_db()
    mentor_id = session["user_id"]

    def get_student_stats(sid):
        info = db.execute("SELECT name, student_code, course FROM students WHERE student_id = ?", (sid,)).fetchone()
        if not info:
            return None
        results = db.execute(
            """SELECT qr.marks, qr.total_questions, qr.accuracy, qr.time_taken,
                      qr.topic, qr.date, qr.status
               FROM quiz_results qr
               JOIN quizzes q ON qr.quiz_id = q.quiz_id
               WHERE qr.student_id = ? AND q.created_by = ? AND q.created_by_type = 'mentor'
               ORDER BY qr.date ASC""",
            (sid, mentor_id),
        ).fetchall()
        if not results:
            return {"info": dict(info), "stats": None}

        scores = [r["accuracy"] for r in results]
        times = [r["time_taken"] for r in results if r["time_taken"] and r["time_taken"] > 0]
        first_half = scores[:len(scores)//2] if len(scores) >= 2 else scores
        second_half = scores[len(scores)//2:] if len(scores) >= 2 else scores
        avg_first = sum(first_half)/len(first_half) if first_half else 0
        avg_second = sum(second_half)/len(second_half) if second_half else 0
        improvement = round(avg_second - avg_first, 1)

        topic_scores = {}
        for r in results:
            t = r["topic"]
            if t not in topic_scores:
                topic_scores[t] = []
            topic_scores[t].append(r["accuracy"])

        return {
            "info": dict(info),
            "stats": {
                "total_quizzes": len(results),
                "avg_accuracy": round(sum(scores)/len(scores), 1),
                "best_score": max(scores),
                "worst_score": min(scores),
                "avg_time": round(sum(times)/len(times)) if times else 0,
                "passed": sum(1 for r in results if r["status"] == "Pass"),
                "failed": sum(1 for r in results if r["status"] == "Fail"),
                "improvement": improvement,
                "topic_averages": {t: round(sum(v)/len(v), 1) for t, v in topic_scores.items()},
                "results": [dict(r) for r in results],
            },
        }

    sa = get_student_stats(student_a_id)
    sb = get_student_stats(student_b_id)
    db.close()

    if not sa or not sb:
        return jsonify({"success": False, "message": "Student not found"}), 404

    # Determine winners per metric
    winners = {}
    if sa["stats"] and sb["stats"]:
        for metric in ["avg_accuracy", "best_score", "total_quizzes", "improvement"]:
            va = sa["stats"].get(metric, 0)
            vb = sb["stats"].get(metric, 0)
            if va > vb:
                winners[metric] = "a"
            elif vb > va:
                winners[metric] = "b"
            else:
                winners[metric] = "tie"
        # Lower time is better
        ta = sa["stats"].get("avg_time", 999)
        tb = sb["stats"].get("avg_time", 999)
        if ta < tb:
            winners["avg_time"] = "a"
        elif tb < ta:
            winners["avg_time"] = "b"
        else:
            winners["avg_time"] = "tie"

    return jsonify({
        "success": True,
        "data": {
            "a": sa,
            "b": sb,
            "winners": winners,
        },
    })


@mentor_bp.route("/api/mentor/calendar-activity")
def calendar_activity():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    mentor_id = session["user_id"]
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if not month or not year:
        from datetime import datetime
        now = datetime.now()
        month, year = now.month, now.year

    from datetime import datetime as dt, timedelta
    first_day = dt(year, month, 1)
    if month == 12:
        last_day = dt(year + 1, 1, 1)
    else:
        last_day = dt(year, month + 1, 1)

    # Get all quiz activity for the month
    activity = db.execute(
        """SELECT DATE(qr.date) as day, COUNT(*) as total,
                  SUM(CASE WHEN qr.status = 'Pass' THEN 1 ELSE 0 END) as passed,
                  SUM(CASE WHEN qr.status = 'Fail' THEN 1 ELSE 0 END) as failed,
                  ROUND(AVG(qr.accuracy), 1) as avg_accuracy
           FROM quiz_results qr
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
             AND qr.date >= ? AND qr.date < ?
           GROUP BY DATE(qr.date) ORDER BY day""",
        (mentor_id, first_day.strftime("%Y-%m-%d"), last_day.strftime("%Y-%m-%d")),
    ).fetchall()

    # Get day-of-week summary
    dow_stats = db.execute(
        """SELECT CAST(strftime('%w', qr.date) AS INTEGER) as day_num,
                  COUNT(*) as total,
                  SUM(CASE WHEN qr.status = 'Pass' THEN 1 ELSE 0 END) as passed
           FROM quiz_results qr
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
             AND qr.date >= ? AND qr.date < ?
           GROUP BY day_num ORDER BY day_num""",
        (mentor_id, first_day.strftime("%Y-%m-%d"), last_day.strftime("%Y-%m-%d")),
    ).fetchall()

    # Get per-student daily activity
    student_daily = db.execute(
        """SELECT s.name, DATE(qr.date) as day, qr.status
           FROM quiz_results qr
           JOIN students s ON qr.student_id = s.student_id
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
             AND qr.date >= ? AND qr.date < ?
           ORDER BY qr.date""",
        (mentor_id, first_day.strftime("%Y-%m-%d"), last_day.strftime("%Y-%m-%d")),
    ).fetchall()

    db.close()

    # Build calendar grid
    calendar_data = {}
    for a in activity:
        day_str = a["day"]
        calendar_data[day_str] = {
            "total": a["total"],
            "passed": a["passed"],
            "failed": a["failed"],
            "avg_accuracy": a["avg_accuracy"],
        }

    # Day names
    dow_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    dow_summary = {}
    for d in dow_stats:
        dow_summary[dow_names[d["day_num"]]] = {"total": d["total"], "passed": d["passed"]}

    return jsonify({
        "success": True,
        "data": {
            "month": month,
            "year": year,
            "calendar": calendar_data,
            "dow_summary": dow_summary,
            "student_daily": [dict(s) for s in student_daily],
            "month_name": first_day.strftime("%B"),
        },
    })


@mentor_bp.route("/api/mentor/leaderboard")
def mentor_leaderboard():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    mentor_id = session["user_id"]

    students = db.execute(
        """SELECT s.student_id, s.name, s.student_code,
                  COUNT(qr.result_id) as total_quizzes,
                  ROUND(AVG(qr.accuracy), 1) as avg_accuracy,
                  MAX(qr.accuracy) as best_score,
                  MIN(qr.accuracy) as worst_score,
                  SUM(CASE WHEN qr.status = 'Pass' THEN 1 ELSE 0 END) as passed,
                  SUM(CASE WHEN qr.status = 'Fail' THEN 1 ELSE 0 END) as failed,
                  (SELECT qr2.accuracy FROM quiz_results qr2
                   JOIN quizzes q2 ON qr2.quiz_id = q2.quiz_id
                   WHERE qr2.student_id = s.student_id AND q2.created_by = ?
                   ORDER BY qr2.date DESC LIMIT 1) as last_score
           FROM students s
           JOIN quiz_results qr ON s.student_id = qr.student_id
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           GROUP BY s.student_id
           ORDER BY avg_accuracy DESC""",
        (mentor_id, mentor_id),
    ).fetchall()

    # Calculate ranks with tie handling
    leaderboard = []
    rank = 1
    prev_score = None
    for i, s in enumerate(students):
        score = s["avg_accuracy"]
        if prev_score is not None and score == prev_score:
            actual_rank = leaderboard[-1]["rank"]
        else:
            actual_rank = i + 1
        prev_score = score

        leaderboard.append({
            "rank": actual_rank,
            "student_id": s["student_id"],
            "name": s["name"],
            "student_code": s["student_code"],
            "total_quizzes": s["total_quizzes"],
            "avg_accuracy": s["avg_accuracy"],
            "best_score": s["best_score"],
            "worst_score": s["worst_score"],
            "passed": s["passed"],
            "failed": s["failed"],
            "last_score": s["last_score"] or 0,
        })

    # Summary stats
    total_students = len(leaderboard)
    avg_all = round(sum(s["avg_accuracy"] for s in leaderboard) / total_students, 1) if total_students else 0
    top_score = leaderboard[0]["avg_accuracy"] if leaderboard else 0
    top_name = leaderboard[0]["name"] if leaderboard else "N/A"
    low_score = leaderboard[-1]["avg_accuracy"] if leaderboard else 0
    low_name = leaderboard[-1]["name"] if leaderboard else "N/A"

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "leaderboard": leaderboard,
            "stats": {
                "total_students": total_students,
                "avg_score": avg_all,
                "top_score": top_score,
                "top_name": top_name,
                "low_score": low_score,
                "low_name": low_name,
            },
        },
    })


@mentor_bp.route("/api/mentor/students")
def mentor_students():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    data = db.execute(
        """SELECT s.student_id, s.name, s.email, s.course, s.student_code,
                  COUNT(qr.result_id) as quiz_count,
                  ROUND(AVG(qr.accuracy), 2) as avg_accuracy,
                  SUM(CASE WHEN qr.status='Pass' THEN 1 ELSE 0 END) as passed
           FROM students s
           LEFT JOIN quiz_results qr ON s.student_id = qr.student_id
           GROUP BY s.student_id ORDER BY avg_accuracy DESC"""
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(d) for d in data]})


@mentor_bp.route("/api/mentor/assign-badge", methods=["POST"])
def assign_badge():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json()
    student_id = data.get("student_id")
    badge_name = data.get("badge_name", "").strip()
    badge_icon = data.get("badge_icon", "🏆")
    description = data.get("description", "").strip()
    if not student_id or not badge_name:
        return jsonify({"success": False, "message": "Student ID and badge name required"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO badges (student_id, mentor_id, badge_name, badge_icon, description) VALUES (?, ?, ?, ?, ?)",
        (student_id, session["user_id"], badge_name, badge_icon, description),
    )
    db.commit()
    badge_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    badge = db.execute("SELECT * FROM badges WHERE badge_id = ?", (badge_id,)).fetchone()
    db.close()
    return jsonify({"success": True, "data": dict(badge), "message": "Badge assigned successfully!"})


@mentor_bp.route("/api/mentor/badges")
def mentor_badges():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    data = db.execute(
        """SELECT b.*, s.name as student_name, s.email as student_email
           FROM badges b JOIN students s ON b.student_id = s.student_id
           WHERE b.mentor_id = ? ORDER BY b.created_at DESC""",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(d) for d in data]})


# ─── FEEDBACK ──────────────────────────────────────────────────────────

@mentor_bp.route("/api/mentor/submit-feedback", methods=["POST"])
def submit_feedback():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json()
    student_id = data.get("student_id")
    rating = data.get("rating")
    comment = data.get("comment", "").strip()
    if not student_id or not rating:
        return jsonify({"success": False, "message": "Student ID and rating required"}), 400
    try:
        rating = int(rating)
        if rating < 1 or rating > 5:
            return jsonify({"success": False, "message": "Rating must be between 1 and 5"}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid rating"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO feedback (student_id, mentor_id, rating, comment) VALUES (?, ?, ?, ?)",
        (student_id, session["user_id"], rating, comment),
    )
    db.commit()
    fb_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    fb = db.execute(
        """SELECT f.*, m.mentor_name FROM feedback f
           JOIN mentors m ON f.mentor_id = m.mentor_id
           WHERE f.feedback_id = ?""",
        (fb_id,),
    ).fetchone()
    db.close()
    return jsonify({"success": True, "data": dict(fb), "message": "Feedback submitted!"})


@mentor_bp.route("/api/mentor/feedbacks")
def mentor_feedbacks():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    data = db.execute(
        """SELECT f.*, s.name as student_name, s.email as student_email
           FROM feedback f JOIN students s ON f.student_id = s.student_id
           WHERE f.mentor_id = ? ORDER BY f.created_at DESC""",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(d) for d in data]})


# ─── QUIZZES MANAGEMENT ───────────────────────────────────────────────

@mentor_bp.route("/api/mentor/quizzes")
def mentor_quizzes():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    quizzes = db.execute(
        """SELECT q.*, (SELECT COUNT(*) FROM questions WHERE quiz_id = q.quiz_id) as question_count
           FROM quizzes q
           WHERE q.created_by = ? AND q.created_by_type = 'mentor'
           ORDER BY q.created_date DESC""",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(q) for q in quizzes]})


@mentor_bp.route("/api/mentor/quiz/<int:quiz_id>", methods=["GET"])
def mentor_get_quiz(quiz_id):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    quiz = db.execute(
        "SELECT * FROM quizzes WHERE quiz_id = ? AND created_by = ?",
        (quiz_id, session["user_id"]),
    ).fetchone()
    if not quiz:
        db.close()
        return jsonify({"success": False, "message": "Quiz not found"}), 404
    questions = db.execute(
        "SELECT * FROM questions WHERE quiz_id = ? ORDER BY question_id",
        (quiz_id,),
    ).fetchall()
    db.close()
    return jsonify({
        "success": True,
        "data": {
            "quiz": dict(quiz),
            "questions": [dict(q) for q in questions],
        },
    })


@mentor_bp.route("/api/mentor/quiz/<int:quiz_id>", methods=["PUT"])
def mentor_update_quiz(quiz_id):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json()
    topic = data.get("topic", "").strip()
    subject = data.get("subject", "").strip()
    difficulty = data.get("difficulty", "Easy")
    questions_data = data.get("questions", [])

    if not topic or not questions_data:
        return jsonify({"success": False, "message": "Topic and questions required"}), 400

    db = get_db()
    quiz = db.execute(
        "SELECT * FROM quizzes WHERE quiz_id = ? AND created_by = ?",
        (quiz_id, session["user_id"]),
    ).fetchone()
    if not quiz:
        db.close()
        return jsonify({"success": False, "message": "Quiz not found"}), 404

    db.execute(
        "UPDATE quizzes SET topic=?, subject=?, difficulty=? WHERE quiz_id=?",
        (topic, subject, difficulty, quiz_id),
    )

    db.execute("DELETE FROM questions WHERE quiz_id = ?", (quiz_id,))
    for q in questions_data:
        db.execute(
            """INSERT INTO questions
               (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                quiz_id,
                q["question_text"],
                q["option_a"],
                q["option_b"],
                q["option_c"],
                q["option_d"],
                q["correct_answer"],
                q.get("difficulty", difficulty),
            ),
        )

    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Quiz updated successfully!"})


@mentor_bp.route("/api/mentor/quiz/<int:quiz_id>", methods=["DELETE"])
def mentor_delete_quiz(quiz_id):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    quiz = db.execute(
        "SELECT * FROM quizzes WHERE quiz_id = ? AND created_by = ?",
        (quiz_id, session["user_id"]),
    ).fetchone()
    if not quiz:
        db.close()
        return jsonify({"success": False, "message": "Quiz not found"}), 404
    db.execute("DELETE FROM questions WHERE quiz_id = ?", (quiz_id,))
    db.execute("DELETE FROM quiz_results WHERE quiz_id = ?", (quiz_id,))
    db.execute("DELETE FROM quizzes WHERE quiz_id = ?", (quiz_id,))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Quiz deleted successfully!"})


# ═══════════════════════════════════════════════════════════════════
# ACCESS CODE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

@mentor_bp.route("/api/mentor/access-codes")
def mentor_access_codes():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    codes = db.execute(
        """SELECT ac.*, q.topic as quiz_name, q.subject as quiz_subject, q.difficulty as quiz_difficulty,
                  (SELECT COUNT(*) FROM questions WHERE quiz_id = ac.quiz_id) as question_count,
                  (SELECT COUNT(*) FROM code_usage_log WHERE code_id = ac.code_id) as used_count
           FROM access_codes ac
           JOIN quizzes q ON ac.quiz_id = q.quiz_id
           WHERE q.created_by = ?
           ORDER BY ac.created_date DESC""",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(c) for c in codes]})


@mentor_bp.route("/api/mentor/access-code/<int:code_id>/disable", methods=["POST"])
def disable_access_code(code_id):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    code = db.execute(
        "SELECT ac.* FROM access_codes ac JOIN quizzes q ON ac.quiz_id = q.quiz_id WHERE ac.code_id = ? AND q.created_by = ?",
        (code_id, session["user_id"]),
    ).fetchone()
    if not code:
        db.close()
        return jsonify({"success": False, "message": "Code not found"}), 404
    db.execute("UPDATE access_codes SET status = 'disabled' WHERE code_id = ?", (code_id,))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Code disabled"})


@mentor_bp.route("/api/mentor/access-code/<int:code_id>/expire", methods=["POST"])
def expire_access_code(code_id):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    code = db.execute(
        "SELECT ac.* FROM access_codes ac JOIN quizzes q ON ac.quiz_id = q.quiz_id WHERE ac.code_id = ? AND q.created_by = ?",
        (code_id, session["user_id"]),
    ).fetchone()
    if not code:
        db.close()
        return jsonify({"success": False, "message": "Code not found"}), 404
    db.execute("UPDATE access_codes SET status = 'expired' WHERE code_id = ?", (code_id,))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Code expired"})


@mentor_bp.route("/api/mentor/access-code/<int:code_id>/update", methods=["PUT"])
def update_access_code(code_id):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db()
    code = db.execute(
        "SELECT ac.* FROM access_codes ac JOIN quizzes q ON ac.quiz_id = q.quiz_id WHERE ac.code_id = ? AND q.created_by = ?",
        (code_id, session["user_id"]),
    ).fetchone()
    if not code:
        db.close()
        return jsonify({"success": False, "message": "Code not found"}), 404
    start_date = data.get("start_date", code["start_date"])
    start_time = data.get("start_time", code["start_time"])
    expiry_date = data.get("expiry_date", code["expiry_date"])
    expiry_time = data.get("expiry_time", code["expiry_time"])
    max_attempts = data.get("max_attempts", code["max_attempts"])
    db.execute(
        "UPDATE access_codes SET start_date=?, start_time=?, expiry_date=?, expiry_time=?, max_attempts=? WHERE code_id=?",
        (start_date, start_time, expiry_date, expiry_time, max_attempts, code_id),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Code settings updated!"})


@mentor_bp.route("/api/mentor/access-code/<int:quiz_id>/regenerate-backup", methods=["POST"])
def regenerate_backup_code(quiz_id):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    quiz = db.execute(
        "SELECT * FROM quizzes WHERE quiz_id = ? AND created_by = ?",
        (quiz_id, session["user_id"]),
    ).fetchone()
    if not quiz:
        db.close()
        return jsonify({"success": False, "message": "Quiz not found"}), 404
    from database import generate_access_code
    new_code = generate_access_code()
    # Disable old backup codes for this quiz
    db.execute(
        "UPDATE access_codes SET status = 'disabled' WHERE quiz_id = ? AND type = 'backup' AND status = 'active'",
        (quiz_id,),
    )
    db.execute(
        "INSERT INTO access_codes (quiz_id, code, type) VALUES (?, ?, 'backup')",
        (quiz_id, new_code),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "New backup code generated", "backup_code": new_code})


# ═══════════════════════════════════════════════════════════════
# STUDY MATERIALS MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@mentor_bp.route("/api/mentor/materials", methods=["GET"])
def list_materials():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    rows = db.execute(
        """SELECT * FROM study_materials WHERE mentor_id = ? ORDER BY created_date DESC""",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(r) for r in rows]})


@mentor_bp.route("/api/mentor/materials/upload", methods=["POST"])
def upload_material():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    title = request.form.get("title", "").strip()
    if not title:
        return jsonify({"success": False, "message": "Title is required."})
    description = request.form.get("description", "").strip()
    subject = request.form.get("subject", "").strip()
    course = request.form.get("course", "").strip()
    category = request.form.get("category", "").strip()
    visibility = request.form.get("visibility", "public")

    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"success": False, "message": "No file selected."})

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    import secrets, os
    safe_name = secrets.token_hex(12) + "." + ext
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "study_materials")
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, safe_name))
    file_size = os.path.getsize(os.path.join(upload_dir, safe_name))
    if file_size > 20 * 1024 * 1024:
        os.remove(os.path.join(upload_dir, safe_name))
        return jsonify({"success": False, "message": "File size exceeds the maximum limit of 20 MB. Please upload a smaller file."})

    db = get_db()
    db.execute(
        """INSERT INTO study_materials (mentor_id, title, description, subject, course, category, file_type, file_path, file_size, visibility)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session["user_id"], title, description, subject, course, category, ext, safe_name, file_size, visibility),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Material uploaded successfully."})


@mentor_bp.route("/api/mentor/materials/link", methods=["POST"])
def add_material_link():
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json()
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"success": False, "message": "Title is required."})
    link = data.get("link", "").strip()
    if not link:
        return jsonify({"success": False, "message": "Link is required."})
    description = data.get("description", "").strip()
    subject = data.get("subject", "").strip()
    course = data.get("course", "").strip()
    category = data.get("category", "").strip()
    visibility = data.get("visibility", "public")

    # Detect link type
    link_lower = link.lower()
    if "youtube.com" in link_lower or "youtu.be" in link_lower:
        link_type = "youtube"
    elif "drive.google.com" in link_lower:
        link_type = "google_drive"
    elif "onedrive.live.com" in link_lower:
        link_type = "onedrive"
    elif "dropbox.com" in link_lower:
        link_type = "dropbox"
    elif "github.com" in link_lower:
        link_type = "github"
    else:
        link_type = "website"

    db = get_db()
    db.execute(
        """INSERT INTO study_materials (mentor_id, title, description, subject, course, category, file_type, external_link, link_type, visibility)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session["user_id"], title, description, subject, course, category, "link", link, link_type, visibility),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Link added successfully."})


@mentor_bp.route("/api/mentor/materials/<int:mid>", methods=["GET"])
def get_material(mid):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    row = db.execute("SELECT * FROM study_materials WHERE material_id = ? AND mentor_id = ?", (mid, session["user_id"])).fetchone()
    db.close()
    if not row:
        return jsonify({"success": False, "message": "Material not found."})
    return jsonify({"success": True, "data": dict(row)})


@mentor_bp.route("/api/mentor/materials/<int:mid>", methods=["PUT"])
def update_material(mid):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db()
    row = db.execute("SELECT * FROM study_materials WHERE material_id = ? AND mentor_id = ?", (mid, session["user_id"])).fetchone()
    if not row:
        db.close()
        return jsonify({"success": False, "message": "Material not found."})
    db.execute(
        """UPDATE study_materials SET title=?, description=?, subject=?, course=?, category=?, visibility=?, updated_date=datetime('now')
           WHERE material_id=?""",
        (data.get("title", row["title"]), data.get("description", row["description"]),
         data.get("subject", row["subject"]), data.get("course", row["course"]),
         data.get("category", row["category"]), data.get("visibility", row["visibility"]), mid),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Material updated."})


@mentor_bp.route("/api/mentor/materials/<int:mid>/replace", methods=["POST"])
def replace_material_file(mid):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    row = db.execute("SELECT * FROM study_materials WHERE material_id = ? AND mentor_id = ?", (mid, session["user_id"])).fetchone()
    if not row:
        db.close()
        return jsonify({"success": False, "message": "Material not found."})
    file = request.files.get("file")
    if not file or file.filename == "":
        db.close()
        return jsonify({"success": False, "message": "No file selected."})

    # Delete old file
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "study_materials")
    if row["file_path"]:
        old_path = os.path.join(upload_dir, row["file_path"])
        if os.path.isfile(old_path):
            os.remove(old_path)

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    import secrets
    safe_name = secrets.token_hex(12) + "." + ext
    file.save(os.path.join(upload_dir, safe_name))
    file_size = os.path.getsize(os.path.join(upload_dir, safe_name))
    if file_size > 20 * 1024 * 1024:
        os.remove(os.path.join(upload_dir, safe_name))
        db.close()
        return jsonify({"success": False, "message": "File size exceeds the maximum limit of 20 MB."})
    db.execute(
        "UPDATE study_materials SET file_path=?, file_type=?, file_size=?, updated_date=datetime('now') WHERE material_id=?",
        (safe_name, ext, file_size, mid),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "File replaced."})


@mentor_bp.route("/api/mentor/materials/<int:mid>", methods=["DELETE"])
def delete_material(mid):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    row = db.execute("SELECT * FROM study_materials WHERE material_id = ? AND mentor_id = ?", (mid, session["user_id"])).fetchone()
    if not row:
        db.close()
        return jsonify({"success": False, "message": "Material not found."})
    # Delete file
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "study_materials")
    if row["file_path"]:
        fpath = os.path.join(upload_dir, row["file_path"])
        if os.path.isfile(fpath):
            os.remove(fpath)
    db.execute("DELETE FROM study_materials WHERE material_id = ?", (mid,))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Material deleted."})


@mentor_bp.route("/api/mentor/materials/<int:mid>/download")
def mentor_download_material(mid):
    if session.get("role") != "mentor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    row = db.execute("SELECT * FROM study_materials WHERE material_id = ? AND mentor_id = ?", (mid, session["user_id"])).fetchone()
    db.close()
    if not row or not row["file_path"]:
        return jsonify({"success": False, "message": "File not found."})
    # Increment download
    db2 = get_db()
    db2.execute("UPDATE study_materials SET total_downloads = total_downloads + 1 WHERE material_id = ?", (mid,))
    db2.commit()
    db2.close()
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "study_materials")
    return send_from_directory(upload_dir, row["file_path"], as_attachment=True, download_name=row["title"] + "." + row["file_type"])


# Quiz report endpoint moved to app.py for reliability
