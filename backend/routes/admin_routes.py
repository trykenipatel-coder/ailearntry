import os
from datetime import datetime
from flask import Blueprint, request, jsonify, session, send_from_directory
from database import get_db

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/admin/dashboard")
def dashboard():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()

    total_students = db.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    total_mentors = db.execute("SELECT COUNT(*) FROM mentors").fetchone()[0]
    total_quizzes = db.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0]
    total_attempts = db.execute("SELECT COUNT(*) FROM quiz_results").fetchone()[0]

    avg_accuracy = db.execute(
        "SELECT COALESCE(AVG(accuracy), 0) FROM quiz_results"
    ).fetchone()[0]

    recent_students = db.execute(
        "SELECT * FROM students ORDER BY registration_date DESC LIMIT 5"
    ).fetchall()

    recent_mentors = db.execute(
        "SELECT * FROM mentors ORDER BY mentor_id DESC LIMIT 5"
    ).fetchall()

    total_materials = db.execute("SELECT COUNT(*) FROM study_materials").fetchone()[0]

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "total_students": total_students,
            "total_mentors": total_mentors,
            "total_quizzes": total_quizzes,
            "total_attempts": total_attempts,
            "avg_accuracy": round(avg_accuracy, 2),
            "total_materials": total_materials,
            "recent_students": [dict(s) for s in recent_students],
            "recent_mentors": [dict(m) for m in recent_mentors],
        },
    })


@admin_bp.route("/api/admin/manage-students")
def manage_students():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    students = db.execute(
        """SELECT s.*,
                  COUNT(qr.result_id) as quiz_count,
                  ROUND(AVG(qr.accuracy), 2) as avg_accuracy
           FROM students s
           LEFT JOIN quiz_results qr ON s.student_id = qr.student_id
           GROUP BY s.student_id ORDER BY s.registration_date DESC"""
    ).fetchall()
    db.close()

    return jsonify({
        "success": True,
        "data": [dict(s) for s in students],
    })


@admin_bp.route("/api/admin/manage-mentors")
def manage_mentors():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    mentors = db.execute(
        """SELECT m.*,
                  COUNT(q.quiz_id) as quiz_count
           FROM mentors m
           LEFT JOIN quizzes q ON m.mentor_id = q.created_by AND q.created_by_type = 'mentor'
           GROUP BY m.mentor_id ORDER BY m.mentor_id DESC"""
    ).fetchall()
    db.close()

    return jsonify({
        "success": True,
        "data": [dict(m) for m in mentors],
    })


@admin_bp.route("/api/admin/student/<int:student_id>", methods=["GET"])
def get_student(student_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
    db.close()
    if not student:
        return jsonify({"success": False, "message": "Student not found"}), 404
    return jsonify({"success": True, "data": dict(student)})


@admin_bp.route("/api/admin/student/<int:student_id>", methods=["PUT"])
def update_student(student_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    course = data.get("course", "").strip()
    if not name or not email:
        return jsonify({"success": False, "message": "Name and email are required"}), 400
    db = get_db()
    db.execute("UPDATE students SET name=?, email=?, course=? WHERE student_id=?",
               (name, email, course, student_id))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Student updated successfully"})


@admin_bp.route("/api/admin/delete-student/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    db.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    db.commit()
    db.close()

    return jsonify({"success": True, "message": "Student deleted"})


@admin_bp.route("/api/admin/delete-mentor/<int:mentor_id>", methods=["DELETE"])
def delete_mentor(mentor_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()
    db.execute("DELETE FROM mentors WHERE mentor_id = ?", (mentor_id,))
    db.commit()
    db.close()

    return jsonify({"success": True, "message": "Mentor deleted"})


@admin_bp.route("/api/admin/approve-mentor/<int:mentor_id>", methods=["POST"])
def approve_mentor(mentor_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    db.execute(
        "UPDATE mentors SET status='active', approved_by=?, approved_at=datetime('now') WHERE mentor_id=? AND status='pending'",
        (session.get("user_id"), mentor_id),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Mentor approved"})


@admin_bp.route("/api/admin/reject-mentor/<int:mentor_id>", methods=["POST"])
def reject_mentor(mentor_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    db.execute(
        "UPDATE mentors SET status='rejected', approved_by=?, approved_at=datetime('now') WHERE mentor_id=? AND status='pending'",
        (session.get("user_id"), mentor_id),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Mentor rejected"})


@admin_bp.route("/api/admin/suspend-mentor/<int:mentor_id>", methods=["POST"])
def suspend_mentor(mentor_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    db.execute(
        "UPDATE mentors SET status='suspended' WHERE mentor_id=? AND status='active'",
        (mentor_id,),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Mentor suspended"})


@admin_bp.route("/api/admin/reactivate-mentor/<int:mentor_id>", methods=["POST"])
def reactivate_mentor(mentor_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    db.execute(
        "UPDATE mentors SET status='active' WHERE mentor_id=? AND status IN ('suspended','rejected')",
        (mentor_id,),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Mentor reactivated"})


@admin_bp.route("/api/admin/mentor/<int:mentor_id>", methods=["GET"])
def get_mentor(mentor_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    mentor = db.execute("SELECT * FROM mentors WHERE mentor_id = ?", (mentor_id,)).fetchone()
    db.close()
    if not mentor:
        return jsonify({"success": False, "message": "Mentor not found"}), 404
    return jsonify({"success": True, "data": dict(mentor)})


@admin_bp.route("/api/admin/mentor/<int:mentor_id>", methods=["PUT"])
def update_mentor(mentor_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    subject = data.get("subject", "").strip()
    if not name or not email:
        return jsonify({"success": False, "message": "Name and email are required"}), 400
    db = get_db()
    db.execute("UPDATE mentors SET mentor_name=?, email=?, subject=? WHERE mentor_id=?",
               (name, email, subject, mentor_id))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Mentor updated successfully"})


@admin_bp.route("/api/admin/mentor-analytics")
def mentor_analytics():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()

    total = db.execute("SELECT COUNT(*) FROM mentors").fetchone()[0]
    with_quizzes = db.execute("SELECT COUNT(DISTINCT created_by) FROM quizzes WHERE created_by_type='mentor'").fetchone()[0]
    total_quizzes = db.execute("SELECT COUNT(*) FROM quizzes WHERE created_by_type='mentor'").fetchone()[0]
    avg_quizzes = round(total_quizzes / total, 1) if total else 0

    # Weekly activity (quizzes created per day, last 7 days)
    weekly = db.execute("""
        SELECT DATE(created_date) as day, COUNT(*) as count
        FROM quizzes WHERE created_by_type='mentor'
        AND created_date >= datetime('now', '-7 days')
        GROUP BY DATE(created_date) ORDER BY day ASC
    """).fetchall()

    # Top mentors by quizzes
    top = db.execute("""
        SELECT m.mentor_name, m.email, m.subject, COUNT(q.quiz_id) as quiz_count
        FROM mentors m LEFT JOIN quizzes q ON m.mentor_id = q.created_by AND q.created_by_type='mentor'
        GROUP BY m.mentor_id ORDER BY quiz_count DESC LIMIT 5
    """).fetchall()

    db.close()
    return jsonify({
        "success": True,
        "data": {
            "total_mentors": total,
            "mentors_with_quizzes": with_quizzes,
            "total_quizzes_created": total_quizzes,
            "avg_quizzes_per_mentor": avg_quizzes,
            "weekly_activity": [dict(w) for w in weekly],
            "top_mentors": [dict(t) for t in top],
        },
    })


@admin_bp.route("/api/admin/mentor-analytics/<int:mentor_id>")
def mentor_analytics_detail(mentor_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()

    mentor = db.execute("SELECT * FROM mentors WHERE mentor_id = ?", (mentor_id,)).fetchone()
    if not mentor:
        db.close()
        return jsonify({"success": False, "message": "Mentor not found"}), 404
    mentor = dict(mentor)

    quizzes = db.execute("SELECT * FROM quizzes WHERE created_by=? AND created_by_type='mentor' ORDER BY created_date DESC",
                         (mentor_id,)).fetchall()

    quiz_count = len(quizzes)
    total_questions = db.execute("""
        SELECT COUNT(*) FROM questions q
        JOIN quizzes qz ON q.quiz_id = qz.quiz_id
        WHERE qz.created_by=? AND qz.created_by_type='mentor'
    """, (mentor_id,)).fetchone()[0]

    avg_difficulty = db.execute("""
        SELECT difficulty, COUNT(*) as count FROM quizzes
        WHERE created_by=? AND created_by_type='mentor'
        GROUP BY difficulty
    """, (mentor_id,)).fetchall()

    # Results from student attempts on this mentor's quizzes
    results = db.execute("""
        SELECT COUNT(*) as total_attempts,
               COALESCE(ROUND(AVG(qr.accuracy), 2), 0) as avg_accuracy,
               SUM(CASE WHEN qr.status='Pass' THEN 1 ELSE 0 END) as passes,
               SUM(CASE WHEN qr.status='Fail' THEN 1 ELSE 0 END) as fails
        FROM quiz_results qr
        JOIN quizzes qz ON qr.quiz_id = qz.quiz_id
        WHERE qz.created_by=? AND qz.created_by_type='mentor'
    """, (mentor_id,)).fetchone()

    db.close()
    return jsonify({
        "success": True,
        "data": {
            "mentor": mentor,
            "quiz_count": quiz_count,
            "total_questions": total_questions,
            "difficulty_distribution": [dict(d) for d in avg_difficulty],
            "results": dict(results),
        },
    })


# ─── ANNOUNCEMENTS ────────────────────────────────────────────────────

@admin_bp.route("/api/admin/announcements", methods=["GET"])
def admin_get_announcements():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    data = db.execute(
        "SELECT * FROM announcements ORDER BY created_at DESC"
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(d) for d in data]})


@admin_bp.route("/api/admin/announcement", methods=["POST"])
def admin_create_announcement():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    data = request.get_json()
    title = data.get("title", "").strip()
    message = data.get("message", "").strip()
    if not title or not message:
        return jsonify({"success": False, "message": "Title and message required"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO announcements (title, message, created_by) VALUES (?, ?, ?)",
        (title, message, session["user_id"]),
    )
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Announcement posted!"})


@admin_bp.route("/api/admin/announcement/<int:ann_id>", methods=["DELETE"])
def admin_delete_announcement(ann_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    db.execute("DELETE FROM announcements WHERE announcement_id = ?", (ann_id,))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Announcement deleted"})


@admin_bp.route("/api/admin/analytics")
def analytics():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    db = get_db()

    pass_fail = db.execute(
        """SELECT status, COUNT(*) as count FROM quiz_results GROUP BY status"""
    ).fetchall()

    difficulty_analysis = db.execute(
        """SELECT q.difficulty, COUNT(qr.result_id) as attempts,
                  ROUND(AVG(qr.accuracy), 2) as avg_accuracy
           FROM quizzes q JOIN quiz_results qr ON q.quiz_id = qr.quiz_id
           GROUP BY q.difficulty"""
    ).fetchall()

    daily_activity = db.execute(
        """SELECT DATE(date) as day, COUNT(*) as attempts
           FROM quiz_results GROUP BY DATE(date) ORDER BY day DESC LIMIT 7"""
    ).fetchall()

    db.close()

    return jsonify({
        "success": True,
        "data": {
            "pass_fail": [dict(pf) for pf in pass_fail],
            "difficulty_analysis": [dict(d) for d in difficulty_analysis],
            "daily_activity": [dict(da) for da in daily_activity],
        },
    })


# ═══════════════════════════════════════════════════════════════
# ADMIN — STUDY MATERIALS
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/api/admin/materials")
def admin_list_materials():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    rows = db.execute(
        """SELECT sm.*, COALESCE(m.mentor_name, 'Unknown') as mentor_name
           FROM study_materials sm
           LEFT JOIN mentors m ON sm.mentor_id = m.mentor_id
           ORDER BY sm.created_date DESC"""
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(r) for r in rows]})


@admin_bp.route("/api/admin/materials/<int:mid>/delete", methods=["DELETE"])
def admin_delete_material(mid):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    row = db.execute("SELECT * FROM study_materials WHERE material_id = ?", (mid,)).fetchone()
    if not row:
        db.close()
        return jsonify({"success": False, "message": "Material not found."})
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "study_materials")
    if row["file_path"]:
        fpath = os.path.join(upload_dir, row["file_path"])
        if os.path.isfile(fpath):
            os.remove(fpath)
    db.execute("DELETE FROM study_materials WHERE material_id = ?", (mid,))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Material deleted."})


@admin_bp.route("/api/admin/materials/<int:mid>/download")
def admin_download_material(mid):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    row = db.execute("SELECT * FROM study_materials WHERE material_id = ?", (mid,)).fetchone()
    db.close()
    if not row or not row["file_path"]:
        return jsonify({"success": False, "message": "File not found."})
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "study_materials")
    return send_from_directory(upload_dir, row["file_path"], as_attachment=True, download_name=row["title"] + "." + row["file_type"])


# ═══════════════════════════════════════════════════════════════
# ADMIN — QUIZZES (view all with mentor info)
# ═══════════════════════════════════════════════════════════════

@admin_bp.route("/api/admin/quizzes")
def admin_list_quizzes():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    rows = db.execute(
        """SELECT q.*, COALESCE(m.mentor_name, 'System') as mentor_name
           FROM quizzes q
           LEFT JOIN mentors m ON q.created_by = m.mentor_id AND q.created_by_type = 'mentor'
           ORDER BY q.created_date DESC"""
    ).fetchall()
    db.close()
    return jsonify({"success": True, "data": [dict(r) for r in rows]})


@admin_bp.route("/api/admin/quiz/<int:quiz_id>/delete", methods=["DELETE"])
def admin_delete_quiz(quiz_id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    db = get_db()
    quiz = db.execute("SELECT * FROM quizzes WHERE quiz_id = ?", (quiz_id,)).fetchone()
    if not quiz:
        db.close()
        return jsonify({"success": False, "message": "Quiz not found."})
    db.execute("DELETE FROM questions WHERE quiz_id = ?", (quiz_id,))
    db.execute("DELETE FROM quiz_results WHERE quiz_id = ?", (quiz_id,))
    db.execute("DELETE FROM violations WHERE quiz_id = ?", (quiz_id,))
    db.execute("DELETE FROM access_codes WHERE quiz_id = ?", (quiz_id,))
    db.execute("DELETE FROM code_usage_log WHERE quiz_id = ?", (quiz_id,))
    db.execute("DELETE FROM quizzes WHERE quiz_id = ?", (quiz_id,))
    db.commit()
    db.close()
    return jsonify({"success": True, "message": "Quiz deleted."})


# Quiz report endpoint moved to app.py for reliability
