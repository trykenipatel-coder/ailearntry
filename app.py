import os
import sys
import json
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, session, request, send_from_directory
from config import SECRET_KEY, DEBUG

from database import init_db, seed_sample_data, get_db, seed_demo_dsa_quiz, seed_demo_scorecards, seed_demo_student_results
from backend.services.gemini_service import OPENROUTER_URL, OPENROUTER_HEADERS, get_model, is_available as ai_available

# Initialize Firebase at startup and sync SQLite data
import backend.services.firebase_service as _fb
print(f"[Startup] Firebase available: {_fb.is_available()}")
if _fb.is_available():
    sync_result = _fb.sync_all_from_sqlite()
    if sync_result.get("success"):
        print(f"[Startup] Firebase sync complete: {sync_result['results']}")
    else:
        print(f"[Startup] Firebase sync error: {sync_result.get('message')}")
else:
    print(f"[Startup] Firebase error: {_fb.get_error()}")
from backend.routes.auth import auth_bp
from backend.routes.student_routes import student_bp
from backend.routes.mentor_routes import mentor_bp
from backend.routes.admin_routes import admin_bp
from backend.services.ml_predictor import predict_performance, get_knowledge_gaps
from backend.services.heartbeat_service import analyze_learning_heartbeat
from backend.services.mistake_service import classify_mistakes
from backend.services.momentum_service import analyze_study_momentum
from backend.services.question_quality import score_question_quality
from backend.services.curriculum_optimizer import get_curriculum_order
from backend.services.confidence_estimator import estimate_confidence_gap
from backend.services.speed_clustering import cluster_learning_speed
from backend.services.retention_decay import calculate_retention

app = Flask(__name__, static_folder=None)
app.secret_key = SECRET_KEY
app.debug = DEBUG
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB

app.register_blueprint(auth_bp)
app.register_blueprint(student_bp)
app.register_blueprint(mentor_bp)
app.register_blueprint(admin_bp)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "study_materials")
os.makedirs(UPLOAD_DIR, exist_ok=True)

with app.app_context():
    init_db()
    seed_sample_data()
    seed_demo_dsa_quiz()
    seed_demo_student_results()
    seed_demo_scorecards()
    print(f"[Startup] AI Status: {'Connected (' + get_model() + ')' if ai_available() else 'NOT CONNECTED'}")


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/uploads/<path:filename>")
def serve_upload(filename):
    upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "study_materials")
    return send_from_directory(upload_dir, filename)


@app.route("/<path:filename>")
def serve_frontend(filename):
    if filename.startswith("api/"):
        return jsonify({"success": False, "message": "Not found"}), 404
    file_path = os.path.join(FRONTEND_DIR, filename)
    if os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIR, filename)
    html_path = file_path + ".html"
    if os.path.isfile(html_path):
        return send_from_directory(FRONTEND_DIR, filename + ".html")
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/session")
def check_session():
    if "user_id" in session:
        return jsonify({
            "authenticated": True,
            "role": session.get("role"),
            "name": session.get("name"),
            "email": session.get("email"),
        })
    return jsonify({"authenticated": False})


@app.route("/api/predict")
def predict():
    if "user_id" not in session or session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    student_id = session["user_id"]
    prediction = predict_performance(student_id)
    gaps = get_knowledge_gaps(student_id)
    return jsonify({
        "success": True,
        "prediction": prediction,
        "knowledge_gaps": gaps,
    })


@app.route("/api/monitor/violation", methods=["POST"])
def track_violation():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    quiz_id = data.get("quiz_id")
    source = data.get("source", "")

    from database import get_db
    db = get_db()
    existing = db.execute(
        "SELECT * FROM violations WHERE student_id = ? AND quiz_id = ?",
        (session["user_id"], quiz_id),
    ).fetchone()

    if existing:
        new_count = existing["warning_count"] + 1
        # Preserve first source, update if new one is more specific
        old_src = existing["source"] or ""
        merged = source if not old_src else old_src + "," + source
        db.execute(
            "UPDATE violations SET warning_count = ?, source = ? WHERE violation_id = ?",
            (new_count, merged, existing["violation_id"]),
        )
    else:
        new_count = 1
        db.execute(
            "INSERT INTO violations (student_id, quiz_id, warning_count, source) VALUES (?, ?, ?, ?)",
            (session["user_id"], quiz_id, 1, source),
        )
    db.commit()
    db.close()

    terminated = new_count >= 1

    source_labels = {
        "tab_switch": "Tab switching detected",
        "window_blur": "Window focus lost",
        "devtools": "Developer tools detected",
        "print_screen": "Screenshot / Print Screen attempt detected",
    }
    msg = source_labels.get(source, "Security violation detected")

    # Sync to Firebase
    try:
        from backend.services.firebase_service import log_violation
        log_violation(str(session["user_id"]), str(quiz_id), new_count, source)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "warning_count": new_count,
        "terminated": terminated,
        "message": "Quiz terminated due to multiple violations!" if terminated else f"Warning: {msg}",
    })


# ═════════════════════════════════════════════════════════════════════
# GEMINI API ROUTES
# ═════════════════════════════════════════════════════════════════════

@app.route("/api/gemini/generate-quiz", methods=["POST"])
def gemini_generate_quiz():
    if session.get("role") not in ("mentor", "admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    topic = data.get("topic", "").strip()
    subject = data.get("subject", "").strip()
    num_easy = int(data.get("numEasy", 5))
    num_medium = int(data.get("numMedium", 5))
    num_hard = int(data.get("numHard", 5))

    if not topic:
        return jsonify({"success": False, "message": "Topic required"}), 400

    from backend.services.gemini_service import generate_quiz
    questions = generate_quiz(topic, subject, num_easy, num_medium, num_hard)

    if not questions:
        return jsonify({"success": False, "message": "Failed to generate questions"}), 500

    # Save to SQLite
    from database import get_db as get_sqlite_db
    db = get_sqlite_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO quizzes (topic, subject, difficulty, created_by, created_by_type) VALUES (?, ?, 'Mixed', ?, 'mentor')",
        (topic, subject, session["user_id"]),
    )
    quiz_id = cursor.lastrowid
    for q in questions:
        opts = q.get("options", ["", "", "", ""])
        cursor.execute(
            """INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty, explanation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (quiz_id, q.get("question", ""), opts[0] if len(opts) > 0 else "",
             opts[1] if len(opts) > 1 else "", opts[2] if len(opts) > 2 else "",
             opts[3] if len(opts) > 3 else "", q.get("correctAnswer", ""),
             q.get("difficulty", "Easy"), q.get("explanation", "")),
        )
    db.commit()
    db.close()

    # Save to Firestore if available
    try:
        from backend.services.firebase_service import save_questions as fb_save_questions, create_quiz as fb_create_quiz
        if fb_save_questions and fb_create_quiz:
            fb_create_quiz(quiz_id, subject, topic, session["user_id"], len(questions))
            fb_save_questions(quiz_id, questions)
    except Exception:
        pass

    return jsonify({
        "success": True,
        "message": f"Generated {len(questions)} questions about '{topic}'!",
        "quiz_id": quiz_id,
        "questions": questions,
    })


@app.route("/api/gemini/recommendations", methods=["POST"])
def gemini_recommendations():
    if session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    student_data = data.get("studentData", {})

    from backend.services.gemini_service import generate_recommendation
    recommendations = generate_recommendation(student_data)

    # Store in Firestore analytics collection
    try:
        from backend.services.firebase_service import save_analytics
        save_analytics(session["user_id"], {
            "averageScore": student_data.get("averageScore", 0),
            "strongTopics": recommendations.get("strengths", []),
            "weakTopics": recommendations.get("improvementAreas", []),
            "learningSpeed": recommendations.get("estimatedLearningSpeed", "Medium"),
        })
    except Exception:
        pass

    return jsonify({"success": True, "data": recommendations})


@app.route("/api/gemini/analyze-performance", methods=["POST"])
def gemini_analyze_performance():
    if session.get("role") not in ("student", "mentor", "admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    student_data = data.get("studentData", {})

    from backend.services.gemini_service import analyze_performance
    analysis = analyze_performance(student_data)

    return jsonify({"success": True, "data": analysis})


@app.route("/api/gemini/status")
def gemini_status():
    from backend.services.gemini_service import is_available as gemini_available
    from backend.services.firebase_service import is_available as firebase_available
    return jsonify({
        "gemini": gemini_available(),
        "firebase": firebase_available(),
    })


@app.route("/api/system/status")
def system_status():
    from backend.services.firebase_service import is_available as firebase_ok
    from backend.services.gemini_service import is_available as gemini_ok
    return jsonify({
        "success": True,
        "server": "running",
        "database": "sqlite",
        "gemini": gemini_ok(),
        "firebase": firebase_ok(),
        "session": "user_id" in session,
    })


@app.route("/api/firebase/debug")
def firebase_debug():
    from backend.services.firebase_service import is_available, get_error
    from config import FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, FIREBASE_DATABASE_URL, FIREBASE_STORAGE_BUCKET
    raw_key = os.getenv("FIREBASE_PRIVATE_KEY", "")
    return jsonify({
        "project_id": FIREBASE_PROJECT_ID,
        "client_email": FIREBASE_CLIENT_EMAIL,
        "has_private_key": len(raw_key) > 0,
        "private_key_length": len(raw_key),
        "private_key_starts_with": raw_key[:50] if raw_key else "",
        "private_key_ends_with": raw_key[-30:] if raw_key else "",
        "database_url": FIREBASE_DATABASE_URL,
        "storage_bucket": FIREBASE_STORAGE_BUCKET,
        "firebase_available": is_available(),
        "error": get_error(),
    })


@app.route("/api/firebase/sync")
def firebase_sync():
    from backend.services.firebase_service import sync_all_from_sqlite
    result = sync_all_from_sqlite()
    return jsonify(result)


# ═════════════════════════════════════════════════════════════════════
# ANNOUNCEMENTS
# ═════════════════════════════════════════════════════════════════════

@app.route("/api/announcements")
def get_announcements():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    from database import get_db
    db = get_db()
    data = db.execute(
        "SELECT * FROM announcements WHERE active = 1 ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(d) for d in data]})


# ═════════════════════════════════════════════════════════════════════
# RESEARCH FEATURES
# ═════════════════════════════════════════════════════════════════════

@app.route("/api/research/heartbeat")
def research_heartbeat():
    if "user_id" not in session or session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify({"success": True, "data": analyze_learning_heartbeat(session["user_id"])})


@app.route("/api/research/mistakes")
def research_mistakes():
    if "user_id" not in session or session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify({"success": True, "data": classify_mistakes(session["user_id"])})


@app.route("/api/research/momentum")
def research_momentum():
    if "user_id" not in session or session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify({"success": True, "data": analyze_study_momentum(session["user_id"])})


# ═════════════════════════════════════════════════════════════════════
# 5 NEW RESEARCH FEATURES
# ═════════════════════════════════════════════════════════════════════

@app.route("/api/research/question-quality")
def research_question_quality():
    if session.get("role") not in ("mentor", "admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    quiz_id = request.args.get("quiz_id", type=int)
    return jsonify({"success": True, "data": score_question_quality(quiz_id)})


@app.route("/api/research/curriculum")
def research_curriculum():
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    topic = request.args.get("topic", "")
    return jsonify({"success": True, "data": get_curriculum_order(topic if topic else None)})


@app.route("/api/research/confidence")
def research_confidence():
    if session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify({"success": True, "data": estimate_confidence_gap(session["user_id"])})


@app.route("/api/research/speed-clustering")
def research_speed_clustering():
    if session.get("role") not in ("mentor", "admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify({"success": True, "data": cluster_learning_speed()})


@app.route("/api/research/retention")
def research_retention():
    if session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return jsonify({"success": True, "data": calculate_retention(session["user_id"])})


# ═════════════════════════════════════════════════════════════════════
# QUIZ REPORT (direct in app.py for reliability)
# ═════════════════════════════════════════════════════════════════════

@app.route("/api/mentor/quiz/<int:qid>/report")
def quiz_report(qid):
    try:
        if session.get("role") != "mentor":
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        db = get_db()
        mentor_id = session["user_id"]

        quiz = db.execute(
            "SELECT * FROM quizzes WHERE quiz_id = ? AND created_by = ?",
            (qid, mentor_id),
        ).fetchone()
        if not quiz:
            db.close()
            return jsonify({"success": False, "message": "Quiz not found."})

        mentor = db.execute("SELECT mentor_name FROM mentors WHERE mentor_id = ?", (mentor_id,)).fetchone()
        mentor_name = mentor["mentor_name"] if mentor else "Unknown"

        ac = db.execute("SELECT code FROM access_codes WHERE quiz_id = ? AND type='primary' LIMIT 1", (qid,)).fetchone()
        unique_code = ac["code"] if ac else "N/A"

        results = db.execute(
            """SELECT qr.marks, qr.total_questions, qr.accuracy, qr.status, qr.time_taken, qr.date,
                      s.name as student_name, s.student_code
               FROM quiz_results qr
               JOIN students s ON qr.student_id = s.student_id
               WHERE qr.quiz_id = ?
               ORDER BY qr.date DESC""",
            (qid,),
        ).fetchall()

        total = len(results)
        passed = sum(1 for r in results if r["status"] == "Pass")
        failed = total - passed
        pass_rate = round(passed / total * 100, 1) if total else 0
        avg_acc = round(sum(r["accuracy"] for r in results) / total, 1) if total else 0
        avg_time = round(sum(r["time_taken"] for r in results) / total) if total else 0
        qcount = db.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (qid,)).fetchone()[0]

        # Extract data BEFORE closing connection
        quiz_dict = {}
        for k in quiz.keys():
            quiz_dict[k] = quiz[k]

        results_list = []
        for r in results:
            rd = {}
            for k in r.keys():
                rd[k] = r[k]
            results_list.append(rd)

        db.close()

        return jsonify({
            "success": True,
            "data": {
                "quiz": quiz_dict,
                "mentor_name": mentor_name,
                "unique_code": unique_code,
                "results": results_list,
                "stats": {
                    "total_attempts": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": pass_rate,
                    "avg_accuracy": avg_acc,
                    "avg_time": avg_time,
                    "question_count": qcount,
                }
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/admin/quiz/<int:qid>/report")
def admin_quiz_report(qid):
    try:
        if session.get("role") != "admin":
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        db = get_db()

        quiz = db.execute("SELECT * FROM quizzes WHERE quiz_id = ?", (qid,)).fetchone()
        if not quiz:
            db.close()
            return jsonify({"success": False, "message": "Quiz not found."})

        mentor = db.execute("SELECT mentor_name FROM mentors WHERE mentor_id = ?", (quiz["created_by"],)).fetchone()
        mentor_name = mentor["mentor_name"] if mentor else "Unknown"

        ac = db.execute("SELECT code FROM access_codes WHERE quiz_id = ? AND type='primary' LIMIT 1", (qid,)).fetchone()
        unique_code = ac["code"] if ac else "N/A"

        results = db.execute(
            """SELECT qr.marks, qr.total_questions, qr.accuracy, qr.status, qr.time_taken, qr.date,
                      s.name as student_name, s.student_code
               FROM quiz_results qr
               JOIN students s ON qr.student_id = s.student_id
               WHERE qr.quiz_id = ?
               ORDER BY qr.date DESC""",
            (qid,),
        ).fetchall()

        total = len(results)
        passed = sum(1 for r in results if r["status"] == "Pass")
        failed = total - passed
        pass_rate = round(passed / total * 100, 1) if total else 0
        avg_acc = round(sum(r["accuracy"] for r in results) / total, 1) if total else 0
        avg_time = round(sum(r["time_taken"] for r in results) / total) if total else 0
        qcount = db.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (qid,)).fetchone()[0]

        quiz_dict = {}
        for k in quiz.keys():
            quiz_dict[k] = quiz[k]

        results_list = []
        for r in results:
            rd = {}
            for k in r.keys():
                rd[k] = r[k]
            results_list.append(rd)

        db.close()

        return jsonify({
            "success": True,
            "data": {
                "quiz": quiz_dict,
                "mentor_name": mentor_name,
                "unique_code": unique_code,
                "results": results_list,
                "stats": {
                    "total_attempts": total,
                    "passed": passed,
                    "failed": failed,
                    "pass_rate": pass_rate,
                    "avg_accuracy": avg_acc,
                    "avg_time": avg_time,
                    "question_count": qcount,
                }
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


import time as _time

def _call_ai_with_retry(system_prompt, user_prompt, max_retries=1):
    """Call OpenRouter AI."""
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers=OPENROUTER_HEADERS,
            json={
                "model": get_model(),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.4,
                "max_tokens": 2048,
            },
            timeout=90,
        )
        if resp.status_code == 200:
            result = resp.json()
            reply = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "reply": reply}
        else:
            err = resp.text[:200]
            print(f"[AI] Chat error {resp.status_code}: {err}")
            if resp.status_code == 429:
                return {"success": False, "message": "AI is rate limited. Please wait 30 seconds and try again."}
            return {"success": False, "message": f"AI error: {resp.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "message": "Cannot reach AI service. Check your internet connection."}
    except requests.exceptions.Timeout:
        return {"success": False, "message": "AI service timed out. Please try again."}
    except Exception as e:
        print(f"[AI] Chat exception: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


# ─── Student Insight Bot ──────────────────────────────────────────────────────

@app.route("/api/student-insight/profile", methods=["GET"])
def insight_student_profile():
    """Fetch full student profile by student_code for the Insight Bot."""
    if session.get("role") not in ("mentor", "admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    code = request.args.get("code", "").strip()
    if not code:
        return jsonify({"success": False, "message": "Student code required"}), 400

    db = get_db()
    try:
        student = db.execute(
            "SELECT student_id, name, email, course, student_code, registration_date FROM students WHERE student_code = ?",
            (code,)
        ).fetchone()
        if not student:
            return jsonify({"success": False, "message": f"Student {code} not found"}), 404

        s_id = student["student_id"]

        quizzes = db.execute("""
            SELECT qr.result_id, qr.quiz_id, qr.marks, qr.total_questions, qr.accuracy,
                   qr.topic, qr.difficulty, qr.time_taken, qr.status, qr.date,
                   q.topic as quiz_topic
            FROM quiz_results qr
            LEFT JOIN quizzes q ON qr.quiz_id = q.quiz_id
            WHERE qr.student_id = ?
            ORDER BY qr.date DESC
        """, (s_id,)).fetchall()

        violations = db.execute("""
            SELECT v.violation_id, v.quiz_id, v.warning_count, v.date, v.source,
                   q.topic as quiz_topic
            FROM violations v
            LEFT JOIN quizzes q ON v.quiz_id = q.quiz_id
            WHERE v.student_id = ?
            ORDER BY v.date DESC
        """, (s_id,)).fetchall()

        streak = db.execute(
            "SELECT current_streak, longest_streak, last_quiz_date FROM student_streaks WHERE student_id = ?",
            (s_id,)
        ).fetchone()

        badges = db.execute("""
            SELECT b.badge_name, b.badge_icon, b.description, b.created_at,
                   m.mentor_name
            FROM badges b
            LEFT JOIN mentors m ON b.mentor_id = m.mentor_id
            WHERE b.student_id = ?
            ORDER BY b.created_at DESC
        """, (s_id,)).fetchall()

        scorecards = db.execute("""
            SELECT sc.cert_id, sc.score, sc.accuracy, sc.mentor_name, sc.generated_at,
                   q.topic as quiz_topic
            FROM scorecards sc
            LEFT JOIN quizzes q ON sc.quiz_id = q.quiz_id
            WHERE sc.student_id = ?
            ORDER BY sc.generated_at DESC
        """, (s_id,)).fetchall()

        total_quizzes = len(quizzes)
        avg_accuracy = sum(q["accuracy"] for q in quizzes) / total_quizzes if total_quizzes > 0 else 0
        avg_time = sum(q["time_taken"] for q in quizzes) / total_quizzes if total_quizzes > 0 else 0
        pass_count = sum(1 for q in quizzes if q["status"] == "Pass")
        topics = list(set(q["topic"] for q in quizzes if q["topic"]))

        topic_stats = {}
        for q in quizzes:
            t = q["topic"]
            if t not in topic_stats:
                topic_stats[t] = {"scores": [], "count": 0}
            topic_stats[t]["scores"].append(q["accuracy"])
            topic_stats[t]["count"] += 1

        topic_summary = {}
        for t, data in topic_stats.items():
            topic_summary[t] = {
                "avg_accuracy": round(sum(data["scores"]) / len(data["scores"]), 1),
                "attempts": data["count"],
                "best": round(max(data["scores"]), 1),
                "worst": round(min(data["scores"]), 1),
            }

        profile = {
            "student": {
                "id": s_id,
                "code": student["student_code"],
                "name": student["name"],
                "email": student["email"],
                "course": student["course"],
                "registered": student["registration_date"],
            },
            "summary": {
                "total_quizzes": total_quizzes,
                "avg_accuracy": round(avg_accuracy, 1),
                "avg_time_seconds": round(avg_time, 0),
                "pass_count": pass_count,
                "fail_count": total_quizzes - pass_count,
                "pass_rate": round(pass_count / total_quizzes * 100, 1) if total_quizzes > 0 else 0,
                "topics": topics,
                "topic_summary": topic_summary,
            },
            "recent_quizzes": [
                {
                    "quiz_id": q["quiz_id"],
                    "topic": q["topic"],
                    "marks": q["marks"],
                    "total": q["total_questions"],
                    "accuracy": q["accuracy"],
                    "difficulty": q["difficulty"],
                    "time_taken": q["time_taken"],
                    "status": q["status"],
                    "date": q["date"],
                }
                for q in quizzes[:10]
            ],
            "violations": [
                {
                    "quiz_id": v["quiz_id"],
                    "quiz_topic": v["quiz_topic"],
                    "warning_count": v["warning_count"],
                    "source": v["source"],
                    "date": v["date"],
                }
                for v in violations[:10]
            ],
            "streak": {
                "current": streak["current_streak"] if streak else 0,
                "longest": streak["longest_streak"] if streak else 0,
                "last_quiz": streak["last_quiz_date"] if streak else None,
            } if streak else None,
            "badges": [
                {
                    "name": b["badge_name"],
                    "icon": b["badge_icon"],
                    "description": b["description"],
                    "mentor": b["mentor_name"],
                    "date": b["created_at"],
                }
                for b in badges
            ],
            "scorecards": [
                {
                    "cert_id": s["cert_id"],
                    "score": s["score"],
                    "accuracy": s["accuracy"],
                    "mentor": s["mentor_name"],
                    "topic": s["quiz_topic"],
                    "date": s["generated_at"],
                }
                for s in scorecards[:5]
            ],
        }
        return jsonify({"success": True, "data": profile})
    finally:
        db.close()


@app.route("/api/student-insight/chat", methods=["POST"])
def insight_chat():
    """AI chat endpoint for Student Insight Bot."""
    if session.get("role") not in ("mentor", "admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json(force=True)
    student_profile = data.get("profile")
    user_message = data.get("message", "").strip()

    if not student_profile or not user_message:
        return jsonify({"success": False, "message": "Profile and message required"}), 400

    if not ai_available():
        return jsonify({"success": False, "message": "AI service is not connected. Please check OpenRouter API key and privacy settings."}), 503

    system_prompt = """You are "Student Insight Bot", an assistant for mentors and admins in an AI learning and exam platform.

You have access to structured data about one student: basic info, quiz history, topic-wise performance, proctoring/violation summaries, badges, and scorecards.

Your job:
- Summarize the student's situation clearly.
- Answer mentor/admin questions based on the data.
- Suggest actions (extra practice, counselling, proctoring review, etc.).
- Identify weak topics, strong topics, and risky behavior.
- Track performance trends over time.

Do not invent data; always base your answers on the provided JSON.
If something is missing, say so clearly.
Use simple professional English.
Be concise but thorough."""

    profile_json = json.dumps(student_profile, indent=2)

    user_prompt = f"""STUDENT DATA (JSON):
{profile_json}

MENTOR/ADMIN MESSAGE:
"{user_message}"

TASK:
Analyze the student data and respond to the mentor/admin message.
Be specific, cite actual numbers, dates, and topics from the data.
Suggest actionable next steps when appropriate."""

    result = _call_ai_with_retry(system_prompt, user_prompt)
    return jsonify(result)


# ─── Exam Strategy & Time-Management Coach Bot ────────────────────────────────

@app.route("/api/exam-coach/profile", methods=["GET"])
def exam_coach_profile():
    """Fetch student's own data + available quizzes for exam strategy."""
    if session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    student_id = session.get("user_id")
    db = get_db()
    try:
        student = db.execute(
            "SELECT student_id, name, email, course, student_code FROM students WHERE student_id = ?",
            (student_id,)
        ).fetchone()
        if not student:
            return jsonify({"success": False, "message": "Student not found"}), 404

        quizzes = db.execute("""
            SELECT qr.quiz_id, qr.marks, qr.total_questions, qr.accuracy,
                   qr.topic, qr.difficulty, qr.time_taken, qr.status, qr.date
            FROM quiz_results qr
            WHERE qr.student_id = ?
            ORDER BY qr.date DESC
        """, (student_id,)).fetchall()

        available_quizzes = db.execute("""
            SELECT q.quiz_id, q.topic, q.subject, q.difficulty, q.status,
                   (SELECT COUNT(*) FROM questions WHERE quiz_id = q.quiz_id) as question_count
            FROM quizzes q
            WHERE q.status = 'published'
            ORDER BY q.created_date DESC
        """).fetchall()

        topic_stats = {}
        for q in quizzes:
            t = q["topic"]
            if t not in topic_stats:
                topic_stats[t] = {"scores": [], "times": [], "count": 0, "difficulties": []}
            topic_stats[t]["scores"].append(q["accuracy"])
            topic_stats[t]["times"].append(q["time_taken"])
            topic_stats[t]["count"] += 1
            topic_stats[t]["difficulties"].append(q["difficulty"])

        topic_analysis = {}
        for t, data in topic_stats.items():
            avg_acc = sum(data["scores"]) / len(data["scores"])
            avg_time = sum(data["times"]) / len(data["times"])
            topic_analysis[t] = {
                "avg_accuracy": round(avg_acc, 1),
                "avg_time_seconds": round(avg_time, 0),
                "attempts": data["count"],
                "strength": "strong" if avg_acc >= 75 else ("medium" if avg_acc >= 50 else "weak"),
                "speed": "fast" if avg_time < 30 else ("normal" if avg_time < 60 else "slow"),
            }

        total_quizzes = len(quizzes)
        overall_avg = sum(q["accuracy"] for q in quizzes) / total_quizzes if total_quizzes > 0 else 0
        overall_avg_time = sum(q["time_taken"] for q in quizzes) / total_quizzes if total_quizzes > 0 else 0

        difficulty_stats = {"Easy": [], "Medium": [], "Hard": []}
        for q in quizzes:
            d = q["difficulty"]
            if d in difficulty_stats:
                difficulty_stats[d].append(q["accuracy"])

        difficulty_analysis = {}
        for d, scores in difficulty_stats.items():
            if scores:
                difficulty_analysis[d] = {
                    "avg_accuracy": round(sum(scores) / len(scores), 1),
                    "attempts": len(scores),
                }

        profile = {
            "student": {
                "name": student["name"],
                "code": student["student_code"],
                "course": student["course"],
            },
            "performance_summary": {
                "total_quizzes": total_quizzes,
                "overall_avg_accuracy": round(overall_avg, 1),
                "overall_avg_time_seconds": round(overall_avg_time, 0),
                "topic_analysis": topic_analysis,
                "difficulty_analysis": difficulty_analysis,
            },
            "available_quizzes": [
                {
                    "quiz_id": q["quiz_id"],
                    "topic": q["topic"],
                    "subject": q["subject"],
                    "difficulty": q["difficulty"],
                    "question_count": q["question_count"],
                }
                for q in available_quizzes[:15]
            ],
            "recent_quizzes": [
                {
                    "topic": q["topic"],
                    "accuracy": q["accuracy"],
                    "difficulty": q["difficulty"],
                    "time_taken": q["time_taken"],
                    "date": q["date"],
                }
                for q in quizzes[:8]
            ],
        }
        return jsonify({"success": True, "data": profile})
    finally:
        db.close()


@app.route("/api/exam-coach/chat", methods=["POST"])
def exam_coach_chat():
    """AI chat endpoint for Exam Strategy Coach."""
    if session.get("role") != "student":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json(force=True)
    student_profile = data.get("profile")
    user_message = data.get("message", "").strip()

    if not student_profile or not user_message:
        return jsonify({"success": False, "message": "Profile and message required"}), 400

    if not ai_available():
        return jsonify({"success": False, "message": "AI service is not connected. Please check OpenRouter API key and privacy settings."}), 503

    system_prompt = """You are "Exam Strategy Coach", an expert exam performance advisor for students.

You are NOT a tutor. You do NOT explain concepts or teach content.

Your expertise is purely about EXAM STRATEGY and TIME MANAGEMENT:
- How to allocate time per section and per question.
- Which question types to attempt first (easy vs hard, high-weight vs low-weight).
- How to avoid silly mistakes under time pressure.
- When to guess vs when to skip.
- How to manage energy and focus during an exam.
- Reading the exam pattern quickly in the first 2 minutes.
- Bubble-sheet / OMR strategy.
- How to handle panic when stuck on a question.

You have the student's past performance data:
- Topic-wise accuracy (strong vs weak topics).
- Speed per topic (fast/normal/slow).
- Difficulty-wise performance (Easy/Medium/Hard accuracy).
- Recent quiz history.

Use this data to give PERSONALIZED strategy advice.

Rules:
- Be direct, actionable, and concise.
- Use bullet points for strategies.
- Give specific time allocations (e.g. "Spend 45 seconds per MCQ").
- Reference the student's actual data when giving advice.
- If the student asks about a specific quiz, use the available quiz data.
- Never explain concepts. Only talk about strategy.
- Use simple, encouraging English."""

    profile_json = json.dumps(student_profile, indent=2)

    user_prompt = f"""STUDENT PERFORMANCE DATA (JSON):
{profile_json}

STUDENT MESSAGE:
"{user_message}"

TASK:
Provide personalized exam strategy advice based on the student's data.
Be specific, reference their actual weak/strong topics and speeds.
Give actionable time management tips."""

    result = _call_ai_with_retry(system_prompt, user_prompt)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=DEBUG)
