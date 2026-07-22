import os
import random
from flask import Blueprint, request, jsonify, session, send_from_directory
from database import get_db
from datetime import datetime, timedelta

student_bp = Blueprint("student", __name__)


def login_required(role):
    if "user_id" not in session or session.get("role") != role:
        return False
    return True


def update_streak(db, student_id):
    today = datetime.now().strftime("%Y-%m-%d")
    streak = db.execute(
        "SELECT * FROM student_streaks WHERE student_id = ?", (student_id,)
    ).fetchone()

    if streak:
        last_date = streak["last_quiz_date"]
        if last_date:
            last = last_date[:10] if len(last_date) >= 10 else last_date
            if last == today:
                return streak["current_streak"]
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            new_streak = streak["current_streak"] + 1 if last == yesterday else 1
        else:
            new_streak = 1
        longest = max(streak["longest_streak"], new_streak)
        db.execute(
            "UPDATE student_streaks SET current_streak=?, longest_streak=?, last_quiz_date=? WHERE student_id=?",
            (new_streak, longest, today, student_id),
        )
    else:
        new_streak = 1
        db.execute(
            "INSERT INTO student_streaks (student_id, current_streak, longest_streak, last_quiz_date) VALUES (?, ?, ?, ?)",
            (student_id, 1, 1, today),
        )
    db.commit()
    return new_streak


@student_bp.route("/api/student/dashboard")
def dashboard():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    student_id = session["user_id"]

    student = db.execute("SELECT student_code FROM students WHERE student_id = ?", (student_id,)).fetchone()

    total_quizzes = db.execute(
        "SELECT COUNT(*) FROM quiz_results WHERE student_id = ?", (student_id,)
    ).fetchone()[0]

    avg_accuracy = db.execute(
        "SELECT COALESCE(AVG(accuracy), 0) FROM quiz_results WHERE student_id = ?",
        (student_id,),
    ).fetchone()[0]

    passed = db.execute(
        "SELECT COUNT(*) FROM quiz_results WHERE student_id = ? AND status = 'Pass'",
        (student_id,),
    ).fetchone()[0]

    failed = total_quizzes - passed

    streak = db.execute(
        "SELECT current_streak, longest_streak FROM student_streaks WHERE student_id = ?",
        (student_id,),
    ).fetchone()

    recent_results = db.execute(
        """SELECT qr.*, q.topic FROM quiz_results qr
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE qr.student_id = ? ORDER BY qr.date DESC LIMIT 5""",
        (student_id,),
    ).fetchall()

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "student_code": student["student_code"] if student else "",
            "total_quizzes": total_quizzes,
            "avg_accuracy": round(avg_accuracy, 2),
            "passed": passed,
            "failed": failed,
            "streak": {
                "current": streak["current_streak"] if streak else 0,
                "longest": streak["longest_streak"] if streak else 0,
            },
            "recent_results": [dict(r) for r in recent_results],
        },
    })


@student_bp.route("/api/student/available-quizzes")
def available_quizzes():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    quizzes = db.execute(
        "SELECT * FROM quizzes WHERE status = 'published' ORDER BY created_date DESC"
    ).fetchall()
    db.close()

    return jsonify({
        "success": True,
        "data": [dict(q) for q in quizzes],
    })


@student_bp.route("/api/student/quiz/<int:quiz_id>/start")
def start_quiz(quiz_id):
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    student_id = session["user_id"]

    quiz = db.execute("SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,)).fetchone()
    if not quiz:
        db.close()
        return jsonify({"success": False, "message": "Quiz not found"}), 404

    questions = db.execute(
        "SELECT * FROM questions WHERE quiz_id = ? ORDER BY question_id",
        (quiz_id,),
    ).fetchall()

    question_list = list(questions)
    random.seed(student_id * 1000 + quiz_id)
    random.shuffle(question_list)

    db.execute(
        "DELETE FROM violations WHERE student_id = ? AND quiz_id = ?",
        (student_id, quiz_id),
    )
    db.commit()

    existing = db.execute(
        "SELECT result_id FROM quiz_results WHERE student_id = ? AND quiz_id = ?",
        (student_id, quiz_id),
    ).fetchone()
    db.close()

    quiz_data = {k: quiz[k] for k in quiz.keys()}
    questions_data = [
        {
            "id": q["question_id"],
            "text": q["question_text"],
            "options": [q["option_a"], q["option_b"], q["option_c"], q["option_d"]],
            "difficulty": q["difficulty"],
        }
        for q in question_list
    ]

    resp = {"success": True, "data": {"quiz": quiz_data, "questions": questions_data}}
    if existing:
        resp["already_completed"] = True
    return jsonify(resp)


@student_bp.route("/api/student/validate-code", methods=["POST"])
def validate_access_code():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    code = data.get("code", "").strip().upper()
    quiz_id = data.get("quiz_id")

    if not code or not quiz_id:
        return jsonify({"success": False, "message": "Code and quiz_id required"}), 400

    db = get_db()
    student_id = session["user_id"]

    # DEMO2026 universal bypass — works on ANY quiz with unlimited attempts
    if code == "DEMO2026":
        try:
            code_record = db.execute(
                "SELECT * FROM access_codes WHERE code = ? AND quiz_id = ?",
                (code, quiz_id),
            ).fetchone()
            if not code_record:
                db.execute(
                    "INSERT INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, 'DEMO2026', 'primary', 'active', 9999)",
                    (quiz_id,),
                )
                db.commit()
                code_record = db.execute(
                    "SELECT * FROM access_codes WHERE code = 'DEMO2026' AND quiz_id = ?",
                    (quiz_id,),
                ).fetchone()
            # Delete any old result so student can re-attempt
            db.execute("DELETE FROM quiz_results WHERE student_id = ? AND quiz_id = ?", (student_id, quiz_id))
            if code_record:
                db.execute("DELETE FROM code_usage_log WHERE code_id = ? AND student_id = ?", (code_record["code_id"], student_id))
            db.commit()
        except Exception as e:
            db.rollback()
        finally:
            db.close()
        return jsonify({"success": True, "message": "DEMO2026 code accepted. Unlimited attempts enabled."})

    # Find the code
    code_record = db.execute(
        "SELECT * FROM access_codes WHERE code = ? AND quiz_id = ?",
        (code, quiz_id),
    ).fetchone()

    if not code_record:
        db.close()
        return jsonify({"success": False, "message": "Invalid access code. Please check and try again."})

    # Check if code is active
    if code_record["status"] != "active":
        labels = {"used": "already been used", "expired": "expired", "disabled": "disabled"}
        msg = labels.get(code_record["status"], "invalid")
        db.close()
        return jsonify({"success": False, "message": f"This access code has been {msg}."})

    # Check if student already used this code
    used = db.execute(
        "SELECT log_id FROM code_usage_log WHERE code_id = ? AND student_id = ?",
        (code_record["code_id"], student_id),
    ).fetchone()
    if used:
        # Allow re-use if max_attempts > 1 (demo/multi-use codes)
        if code_record["max_attempts"] > 1:
            pass  # allow re-use
        else:
            db.close()
            return jsonify({"success": False, "message": "You have already used this access code."})

    # Check time window if set
    from datetime import datetime as dt
    now = dt.now()
    if code_record["start_date"]:
        try:
            start_dt = dt.strptime(code_record["start_date"] + " " + (code_record["start_time"] or "00:00"), "%Y-%m-%d %H:%M")
            if now < start_dt:
                db.close()
                return jsonify({"success": False, "message": "This code is not yet active. Please wait until the start time."})
        except ValueError:
            pass
    if code_record["expiry_date"]:
        try:
            end_dt = dt.strptime(code_record["expiry_date"] + " " + (code_record["expiry_time"] or "23:59"), "%Y-%m-%d %H:%M")
            if now > end_dt:
                db.close()
                return jsonify({"success": False, "message": "This code has expired."})
        except ValueError:
            pass

    # Check if student already completed this quiz
    existing = db.execute(
        "SELECT result_id FROM quiz_results WHERE student_id = ? AND quiz_id = ?",
        (student_id, quiz_id),
    ).fetchone()
    if existing:
        # Allow re-attempts if max_attempts > 1 (demo/multi-use codes)
        if code_record["max_attempts"] > 1:
            # Delete old result so new submission works
            db.execute("DELETE FROM quiz_results WHERE student_id = ? AND quiz_id = ?", (student_id, quiz_id))
        elif code_record["type"] != "backup":
            db.close()
            return jsonify({
                "success": False,
                "message": "You have already completed this quiz. Use a Backup Access Code for another attempt.",
                "already_completed": True,
                "needs_backup": True,
            })
        # Delete old result so new submission works
        db.execute("DELETE FROM quiz_results WHERE student_id = ? AND quiz_id = ?", (student_id, quiz_id))
        db.commit()

    db.close()
    return jsonify({
        "success": True,
        "message": "Access code validated! You may now start the quiz.",
        "code_id": code_record["code_id"],
        "code_type": code_record["type"],
    })


@student_bp.route("/api/student/quiz/submit", methods=["POST"])
def submit_quiz():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    quiz_id = data.get("quiz_id")
    answers = data.get("answers", {})
    time_taken = data.get("time_taken", 0)
    access_code = data.get("access_code", "")

    db = get_db()
    student_id = session["user_id"]

    # Delete old result if this is a re-attempt
    db.execute("DELETE FROM quiz_results WHERE student_id = ? AND quiz_id = ?", (student_id, quiz_id))
    db.commit()

    questions = db.execute(
        "SELECT * FROM questions WHERE quiz_id = ?", (quiz_id,)
    ).fetchall()

    correct = 0
    total = len(questions)
    avg_time_per_q = time_taken / max(total, 1)

    for q in questions:
        user_answer = answers.get(str(q["question_id"]), "").strip()
        is_correct = 1 if user_answer.upper() == q["correct_answer"].strip().upper() else 0
        if is_correct:
            correct += 1

        # Record individual question attempt for adaptive learning
        try:
            db.execute(
                """INSERT INTO question_attempts
                   (student_id, question_id, quiz_id, topic, difficulty, is_correct,
                    response_time, hint_used, attempt_number, confidence, als_score, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, NULL, 0, datetime('now'))""",
                (student_id, q["question_id"], quiz_id, quiz["topic"] if quiz else "",
                 q["difficulty"], is_correct, round(avg_time_per_q, 1))
            )
        except Exception:
            pass

    # Update topic mastery
    try:
        accuracy_pct = (correct / total * 100) if total > 0 else 0
        avg_time = avg_time_per_q
        topic_name = quiz["topic"] if quiz else ""
        existing = db.execute(
            "SELECT * FROM topic_mastery WHERE student_id=? AND topic=?",
            (student_id, topic_name)
        ).fetchone()
        if existing:
            new_total = existing["total_attempts"] + total
            new_correct = existing["correct_count"] + correct
            new_mastery = (new_correct / new_total * 100) if new_total > 0 else 0
            new_avg_time = ((existing["avg_response_time"] * existing["total_attempts"]) + (avg_time * total)) / new_total
            db.execute(
                """UPDATE topic_mastery SET total_attempts=?, correct_count=?,
                   avg_response_time=?, mastery_pct=?, last_attempted=datetime('now')
                   WHERE student_id=? AND topic=?""",
                (new_total, new_correct, round(new_avg_time, 1), round(new_mastery, 1),
                 student_id, topic_name)
            )
        else:
            mastery = (correct / total * 100) if total > 0 else 0
            db.execute(
                """INSERT INTO topic_mastery
                   (student_id, topic, total_attempts, correct_count, avg_response_time,
                    hint_count, mastery_pct, last_attempted)
                   VALUES (?, ?, ?, ?, ?, 0, ?, datetime('now'))""",
                (student_id, topic_name, total, correct, round(avg_time, 1), round(mastery, 1))
            )
    except Exception:
        pass

    accuracy = (correct / total * 100) if total > 0 else 0
    status = "Pass" if accuracy >= 40 else "Fail"

    quiz = db.execute("SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,)).fetchone()

    db.execute(
        """INSERT INTO quiz_results
           (student_id, quiz_id, marks, total_questions, accuracy, topic, difficulty, time_taken, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            student_id,
            quiz_id,
            correct,
            total,
            round(accuracy, 2),
            quiz["topic"],
            quiz["difficulty"],
            time_taken,
            status,
        ),
    )
    db.commit()

    result_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    result = db.execute(
        "SELECT * FROM quiz_results WHERE result_id = ?", (result_id,)
    ).fetchone()

    # Log access code usage if provided
    if access_code:
        code_record = db.execute(
            "SELECT * FROM access_codes WHERE code = ? AND quiz_id = ?",
            (access_code, quiz_id),
        ).fetchone()
        if code_record:
            db.execute(
                "INSERT INTO code_usage_log (code_id, student_id, quiz_id, attempt_type, status) VALUES (?, ?, ?, ?, 'success')",
                (code_record["code_id"], student_id, quiz_id, code_record["type"]),
            )
            db.commit()

    db.execute(
        "DELETE FROM violations WHERE student_id = ? AND quiz_id = ?",
        (student_id, quiz_id),
    )
    # Update streak (same connection to avoid locking)
    try:
        update_streak(db, student_id)
    except Exception:
        db.rollback()
    db.close()

    # Sync to Firebase
    try:
        from backend.services.firebase_service import save_quiz_result
        save_quiz_result(session["user_id"], quiz_id, correct, total,
                          round(accuracy, 2), time_taken, quiz["difficulty"],
                          status, quiz["topic"])
    except Exception:
        pass

    return jsonify({
        "success": True,
        "data": dict(result),
        "summary": {
            "correct": correct,
            "total": total,
            "accuracy": round(accuracy, 2),
            "status": status,
        },
    })


@student_bp.route("/api/student/results")
def get_results():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    results = db.execute(
        """SELECT qr.*, q.topic, q.subject FROM quiz_results qr
           JOIN quizzes q ON qr.quiz_id = q.quiz_id
           WHERE qr.student_id = ? ORDER BY qr.date DESC""",
        (session["user_id"],),
    ).fetchall()
    db.close()

    return jsonify({
        "success": True,
        "data": [dict(r) for r in results],
    })


@student_bp.route("/api/student/performance")
def performance():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    student_id = session["user_id"]

    topic_analysis = db.execute(
        """SELECT topic, COUNT(*) as attempts,
                  ROUND(AVG(accuracy), 2) as avg_accuracy,
                  SUM(CASE WHEN status='Pass' THEN 1 ELSE 0 END) as passed
           FROM quiz_results WHERE student_id = ?
           GROUP BY topic""",
        (student_id,),
    ).fetchall()

    recent_scores = db.execute(
        """SELECT accuracy, date FROM quiz_results
           WHERE student_id = ? ORDER BY date DESC LIMIT 10""",
        (student_id,),
    ).fetchall()

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "topic_analysis": [dict(t) for t in topic_analysis],
            "recent_scores": [dict(s) for s in recent_scores],
        },
    })


@student_bp.route("/api/student/streak")
def get_streak():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    streak = db.execute(
        "SELECT current_streak, longest_streak FROM student_streaks WHERE student_id = ?",
        (session["user_id"],),
    ).fetchone()
    db.close()
    return jsonify({
        "success": True,
        "data": {
            "current": streak["current_streak"] if streak else 0,
            "longest": streak["longest_streak"] if streak else 0,
        },
    })


@student_bp.route("/api/student/badges")
def get_my_badges():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    badges = db.execute(
        """SELECT b.*, m.mentor_name FROM badges b
           JOIN mentors m ON b.mentor_id = m.mentor_id
           WHERE b.student_id = ? ORDER BY b.created_at DESC""",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(b) for b in badges]})


@student_bp.route("/api/leaderboard")
def leaderboard():
    db = get_db()
    try:
        # Check if student_code column exists
        cols = [r[1] for r in db.execute("PRAGMA table_info(students)").fetchall()]
        has_code = "student_code" in cols
        code_col = "s.student_code" if has_code else "'' as student_code"

        top = db.execute(
            f"""SELECT s.student_id, s.name, s.email, {code_col},
                      COUNT(qr.result_id) as quiz_count,
                      ROUND(AVG(qr.accuracy), 2) as avg_accuracy,
                      COALESCE(st.current_streak, 0) as streak
               FROM students s
               LEFT JOIN quiz_results qr ON s.student_id = qr.student_id
               LEFT JOIN student_streaks st ON s.student_id = st.student_id
               GROUP BY s.student_id
               HAVING quiz_count > 0
               ORDER BY avg_accuracy DESC, quiz_count DESC
               LIMIT 10""",
        ).fetchall()
        db.close()
        return jsonify({
            "success": True,
            "data": [dict(t) for t in top],
        })
    except Exception as e:
        db.close()
        return jsonify({"success": True, "data": []})


@student_bp.route("/api/student/feedbacks")
def get_my_feedbacks():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    data = db.execute(
        """SELECT f.*, m.mentor_name FROM feedback f
           JOIN mentors m ON f.mentor_id = m.mentor_id
           WHERE f.student_id = ? ORDER BY f.created_at DESC""",
        (session["user_id"],),
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(d) for d in data]})


# ═══════════════════════════════════════════════════════════════
# STUDY MATERIALS (Student Access)
# ═══════════════════════════════════════════════════════════════

@student_bp.route("/api/student/materials")
def student_materials():
    if session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    rows = db.execute(
        "SELECT * FROM study_materials WHERE status='active' AND visibility='public' ORDER BY created_date DESC"
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(r) for r in rows]})


@student_bp.route("/api/student/materials/<int:mid>")
def student_material_detail(mid):
    if session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    db.execute("UPDATE study_materials SET total_views = total_views + 1 WHERE material_id = ?", (mid,))
    db.commit()
    row = db.execute("SELECT * FROM study_materials WHERE material_id = ? AND status='active' AND visibility='public'", (mid,)).fetchone()
    db.close()
    if not row:
        return jsonify({"success": False, "message": "Material not found."})
    return jsonify({"success": True, "data": dict(row)})


@student_bp.route("/api/student/materials/<int:mid>/download")
def student_download_material(mid):
    if session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    row = db.execute("SELECT * FROM study_materials WHERE material_id = ? AND status='active' AND visibility='public'", (mid,)).fetchone()
    if not row or not row["file_path"]:
        db.close()
        return jsonify({"success": False, "message": "File not found."})
    db.execute("UPDATE study_materials SET total_downloads = total_downloads + 1 WHERE material_id = ?", (mid,))
    db.commit()
    db.close()
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "study_materials")
    return send_from_directory(upload_dir, row["file_path"], as_attachment=True, download_name=row["title"] + "." + row["file_type"])


@student_bp.route("/api/student/leaderboard")
def student_leaderboard():
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    student_id = session["user_id"]

    # Get all students with their avg accuracy across all quizzes
    students = db.execute(
        """SELECT s.student_id, s.name, s.student_code,
                  COUNT(qr.result_id) as total_quizzes,
                  ROUND(AVG(qr.accuracy), 1) as avg_accuracy,
                  MAX(qr.accuracy) as best_score,
                  SUM(CASE WHEN qr.status = 'Pass' THEN 1 ELSE 0 END) as passed,
                  (SELECT qr2.accuracy FROM quiz_results qr2
                   WHERE qr2.student_id = s.student_id
                   ORDER BY qr2.date DESC LIMIT 1) as last_score
           FROM students s
           JOIN quiz_results qr ON s.student_id = qr.student_id
           GROUP BY s.student_id
           ORDER BY avg_accuracy DESC"""
    ).fetchall()

    # Calculate ranks with tie handling
    leaderboard = []
    my_rank = None
    rank = 1
    prev_score = None
    for i, s in enumerate(students):
        score = s["avg_accuracy"]
        if prev_score is not None and score == prev_score:
            actual_rank = leaderboard[-1]["rank"]
        else:
            actual_rank = i + 1
        prev_score = score

        entry = {
            "rank": actual_rank,
            "student_id": s["student_id"],
            "name": s["name"],
            "student_code": s["student_code"],
            "total_quizzes": s["total_quizzes"],
            "avg_accuracy": s["avg_accuracy"],
            "best_score": s["best_score"],
            "passed": s["passed"],
            "last_score": s["last_score"] or 0,
        }
        leaderboard.append(entry)
        if s["student_id"] == student_id:
            my_rank = entry

    # Summary
    total = len(leaderboard)
    avg_all = round(sum(s["avg_accuracy"] for s in leaderboard) / total, 1) if total else 0
    top = leaderboard[0] if leaderboard else None

    # My improvement: compare first half vs second half of my results
    my_results = db.execute(
        """SELECT qr.accuracy FROM quiz_results qr
           WHERE qr.student_id = ?
           ORDER BY qr.date ASC""",
        (student_id,),
    ).fetchall()
    my_scores = [r["accuracy"] for r in my_results]
    improvement = 0
    if len(my_scores) >= 2:
        mid = len(my_scores) // 2
        avg_first = sum(my_scores[:mid]) / mid
        avg_second = sum(my_scores[mid:]) / (len(my_scores) - mid)
        improvement = round(avg_second - avg_first, 1)

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "leaderboard": leaderboard[:20],  # Top 20
            "my_rank": my_rank,
            "stats": {
                "total_students": total,
                "avg_score": avg_all,
                "top_name": top["name"] if top else "N/A",
                "top_score": top["avg_accuracy"] if top else 0,
                "my_improvement": improvement,
            },
        },
    })


@student_bp.route("/api/student/scorecard/<int:quiz_id>")
def generate_scorecard(quiz_id):
    if not login_required("student"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    student_id = session["user_id"]

    # Get student info
    student = db.execute(
        "SELECT name, email, student_code FROM students WHERE student_id = ?",
        (student_id,),
    ).fetchone()
    if not student:
        db.close()
        return jsonify({"success": False, "message": "Student not found"}), 404

    # Get quiz info + mentor name
    quiz = db.execute(
        """SELECT q.topic, q.difficulty, q.created_by,
                  m.mentor_name as mentor_name, m.email as mentor_email
           FROM quizzes q
           JOIN mentors m ON q.created_by = m.mentor_id
           WHERE q.quiz_id = ?""",
        (quiz_id,),
    ).fetchone()
    if not quiz:
        db.close()
        return jsonify({"success": False, "message": "Quiz not found"}), 404

    # Get latest result for this student+quiz
    result = db.execute(
        """SELECT marks, total_questions, accuracy, time_taken, date, status
           FROM quiz_results
           WHERE student_id = ? AND quiz_id = ?
           ORDER BY date DESC LIMIT 1""",
        (student_id, quiz_id),
    ).fetchone()
    if not result:
        db.close()
        return jsonify({"success": False, "message": "No result found"}), 404

    # Generate certificate ID
    import uuid
    from datetime import datetime
    cert_id = "CERT-" + datetime.now().strftime("%Y%m%d") + "-" + str(uuid.uuid4())[:6].upper()

    # Log the scorecard generation
    db.execute(
        """INSERT INTO scorecards (student_id, quiz_id, cert_id, score, accuracy,
                  mentor_name, generated_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
        (student_id, quiz_id, cert_id, result["accuracy"], result["accuracy"],
         quiz["mentor_name"]),
    )
    db.commit()
    db.close()

    return jsonify({
        "success": True,
        "data": {
            "student": {
                "name": student["name"],
                "email": student["email"],
                "student_code": student["student_code"],
            },
            "quiz": {
                "topic": quiz["topic"],
                "difficulty": quiz["difficulty"],
            },
            "result": {
                "marks": result["marks"],
                "total_questions": result["total_questions"],
                "accuracy": result["accuracy"],
                "time_taken": result["time_taken"],
                "date": result["date"],
                "status": result["status"],
            },
            "mentor": {
                "name": quiz["mentor_name"],
                "email": quiz["mentor_email"],
            },
            "cert_id": cert_id,
        },
    })
