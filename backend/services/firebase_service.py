import os
import json
from datetime import datetime

import config

firebase_available = False
firebase_error = ""
db = None
auth_client = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, auth as firebase_auth

    if config.FIREBASE_PROJECT_ID and config.FIREBASE_PRIVATE_KEY and config.FIREBASE_CLIENT_EMAIL:
        private_key = config.FIREBASE_PRIVATE_KEY.replace("\\n", "\n")

        cred_obj = credentials.Certificate({
            "type": "service_account",
            "project_id": config.FIREBASE_PROJECT_ID,
            "private_key": private_key,
            "client_email": config.FIREBASE_CLIENT_EMAIL,
            "token_uri": "https://oauth2.googleapis.com/token",
        })
        firebase_admin.initialize_app(cred_obj, {
            "databaseURL": config.FIREBASE_DATABASE_URL,
            "storageBucket": config.FIREBASE_STORAGE_BUCKET,
        })
        db = firestore.client()
        auth_client = firebase_auth
        list(db.collections())
        firebase_available = True
        print("[Firebase] Initialized and connected successfully")
    else:
        firebase_error = "Missing credentials - check .env file"
        print(f"[Firebase] {firebase_error}")

except ImportError:
    firebase_error = "firebase-admin not installed - run: pip install firebase-admin"
    print(f"[Firebase] {firebase_error}")
except Exception as e:
    firebase_error = str(e)
    print(f"[Firebase] Connection failed: {e}")
    print("[Firebase] Make sure Firestore Database is created in Firebase Console")


def get_error():
    return firebase_error


def is_available():
    return firebase_available


def _check():
    if not firebase_available:
        print("[Firebase] Operation skipped - Firebase not available")
        return False
    return True


# ─── USERS ───────────────────────────────────────────────────────────

def create_user(uid, name, email, role):
    if not _check():
        return None
    try:
        doc_ref = db.collection("users").document(uid)
        doc_ref.set({
            "uid": uid, "name": name, "email": email, "role": role,
            "createdAt": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.get().to_dict()
    except Exception as e:
        print(f"[Firebase] create_user error: {e}")
        return None


def get_user(uid):
    if not _check():
        return None
    try:
        doc = db.collection("users").document(uid).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"[Firebase] get_user error: {e}")
        return None


def get_user_by_email(email):
    if not _check():
        return None
    try:
        docs = db.collection("users").where("email", "==", email).limit(1).stream()
        for doc in docs:
            return doc.to_dict()
        return None
    except Exception as e:
        print(f"[Firebase] get_user_by_email error: {e}")
        return None


def get_all_users(role=None):
    if not _check():
        return []
    try:
        ref = db.collection("users")
        if role:
            ref = ref.where("role", "==", role)
        return [doc.to_dict() for doc in ref.stream()]
    except Exception as e:
        print(f"[Firebase] get_all_users error: {e}")
        return []


def update_user(uid, data):
    if not _check():
        return None
    try:
        db.collection("users").document(uid).update(data)
        return get_user(uid)
    except Exception as e:
        print(f"[Firebase] update_user error: {e}")
        return None


def delete_user(uid):
    if not _check():
        return False
    try:
        db.collection("users").document(uid).delete()
        return True
    except Exception as e:
        print(f"[Firebase] delete_user error: {e}")
        return False


# ─── QUIZZES ─────────────────────────────────────────────────────────

def create_quiz(quiz_id, subject, topic, created_by, total_questions):
    if not _check():
        return None
    try:
        doc_ref = db.collection("quizzes").document(str(quiz_id))
        doc_ref.set({
            "quizId": str(quiz_id), "subject": subject, "topic": topic,
            "createdBy": created_by, "createdAt": firestore.SERVER_TIMESTAMP,
            "totalQuestions": total_questions,
        })
        return doc_ref.get().to_dict()
    except Exception as e:
        print(f"[Firebase] create_quiz error: {e}")
        return None


def get_quiz(quiz_id):
    if not _check():
        return None
    try:
        doc = db.collection("quizzes").document(str(quiz_id)).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"[Firebase] get_quiz error: {e}")
        return None


def get_all_quizzes():
    if not _check():
        return []
    try:
        docs = db.collection("quizzes").order_by("createdAt", direction=firestore.Query.DESCENDING).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[Firebase] get_all_quizzes error: {e}")
        return []


def get_quizzes_by_mentor(mentor_id):
    if not _check():
        return []
    try:
        docs = db.collection("quizzes").where("createdBy", "==", mentor_id).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[Firebase] get_quizzes_by_mentor error: {e}")
        return []


# ─── QUESTIONS ───────────────────────────────────────────────────────

def save_questions(quiz_id, questions):
    if not _check():
        return False
    try:
        batch = db.batch()
        for i, q in enumerate(questions):
            doc_ref = db.collection("questions").document(f"{quiz_id}_q{i}")
            opts = q.get("options") or [q.get("option_a", ""), q.get("option_b", ""), q.get("option_c", ""), q.get("option_d", "")]
            batch.set(doc_ref, {
                "questionId": f"{quiz_id}_q{i}", "quizId": str(quiz_id),
                "question": q.get("question_text") or q.get("question", ""),
                "options": opts if isinstance(opts, list) else ["", "", "", ""],
                "correctAnswer": q.get("correct_answer") or q.get("correctAnswer", ""),
                "difficulty": q.get("difficulty", "Easy"),
                "explanation": q.get("explanation", ""),
            })
        batch.commit()
        print(f"[Firebase] Saved {len(questions)} questions for quiz {quiz_id}")
        return True
    except Exception as e:
        print(f"[Firebase] save_questions error: {e}")
        return False


def get_questions(quiz_id):
    if not _check():
        return []
    try:
        docs = db.collection("questions").where("quizId", "==", str(quiz_id)).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[Firebase] get_questions error: {e}")
        return []


# ─── QUIZ RESULTS ────────────────────────────────────────────────────

def save_quiz_result(student_id, quiz_id, marks, total, accuracy, time_taken, difficulty, status, topic=""):
    if not _check():
        return None
    try:
        result_id = f"{student_id}_{quiz_id}_{int(datetime.now().timestamp())}"
        doc_ref = db.collection("quizResults").document(result_id)
        doc_ref.set({
            "resultId": result_id, "studentId": str(student_id),
            "quizId": str(quiz_id), "marks": marks, "totalQuestions": total,
            "accuracy": accuracy, "timeTaken": time_taken,
            "difficulty": difficulty, "status": status, "topic": topic,
            "date": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.get().to_dict()
    except Exception as e:
        print(f"[Firebase] save_quiz_result error: {e}")
        return None


def get_student_results(student_id):
    if not _check():
        return []
    try:
        docs = db.collection("quizResults").where("studentId", "==", str(student_id)).order_by("date", direction=firestore.Query.DESCENDING).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[Firebase] get_student_results error: {e}")
        return []


def get_all_results():
    if not _check():
        return []
    try:
        docs = db.collection("quizResults").order_by("date", direction=firestore.Query.DESCENDING).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[Firebase] get_all_results error: {e}")
        return []


# ─── ANALYTICS ───────────────────────────────────────────────────────

def save_analytics(student_id, data):
    if not _check():
        return None
    try:
        doc_ref = db.collection("analytics").document(str(student_id))
        doc_ref.set({
            "studentId": str(student_id),
            "averageScore": data.get("averageScore", 0),
            "strongTopics": data.get("strongTopics", []),
            "weakTopics": data.get("weakTopics", []),
            "learningSpeed": data.get("learningSpeed", "Medium"),
            "lastUpdated": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.get().to_dict()
    except Exception as e:
        print(f"[Firebase] save_analytics error: {e}")
        return None


def get_analytics(student_id):
    if not _check():
        return None
    try:
        doc = db.collection("analytics").document(str(student_id)).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"[Firebase] get_analytics error: {e}")
        return None


# ─── VIOLATIONS ──────────────────────────────────────────────────────

def log_violation(student_id, quiz_id, warning_count, source=""):
    if not _check():
        return None
    try:
        doc_ref = db.collection("violations").document(f"{student_id}_{quiz_id}")
        doc_ref.set({
            "studentId": str(student_id), "quizId": str(quiz_id),
            "warningCount": warning_count, "source": source,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.get().to_dict()
    except Exception as e:
        print(f"[Firebase] log_violation error: {e}")
        return None


def get_violations(student_id, quiz_id):
    if not _check():
        return None
    try:
        doc = db.collection("violations").document(f"{student_id}_{quiz_id}").get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f"[Firebase] get_violations error: {e}")
        return None


# ─── FIREBASE AUTH HELPERS ───────────────────────────────────────────

def verify_firebase_token(id_token):
    if not _check() or auth_client is None:
        return None
    try:
        decoded = auth_client.verify_id_token(id_token)
        return decoded
    except Exception as e:
        print(f"[Firebase] Token verification error: {e}")
        return None


def create_firebase_user(email, password, name, role):
    if not _check() or auth_client is None:
        return None
    try:
        user = auth_client.create_user(email=email, password=password, display_name=name)
        auth_client.set_custom_user_claims(user.uid, {"role": role})
        create_user(user.uid, name, email, role)
        return user.uid
    except Exception as e:
        print(f"[Firebase] create_firebase_user error: {e}")
        return None


def get_user_by_firebase_uid(uid):
    if not _check() or auth_client is None:
        return None
    try:
        return auth_client.get_user(uid)
    except Exception as e:
        print(f"[Firebase] get_user_by_firebase_uid error: {e}")
        return None


# ─── SYNC SQLite → Firestore ────────────────────────────────────────

def sync_all_from_sqlite():
    if not _check():
        return {"success": False, "message": "Firebase not available"}

    from database import get_db
    conn = get_db()
    cursor = conn.cursor()
    results = {"users": 0, "quizzes": 0, "questions": 0, "quizResults": 0, "violations": 0, "streaks": 0, "badges": 0, "feedback": 0}

    try:
        # ── Sync Users ──
        for table, role_prefix, id_col, name_col, extra in [
            ("students", "student", "student_id", "name", "course"),
            ("mentors", "mentor", "mentor_id", "mentor_name", "subject"),
            ("admins", "admin", "admin_id", None, None),
        ]:
            rows = [dict(r) for r in cursor.execute(f"SELECT * FROM {table}").fetchall()]
            for r in rows:
                uid = f"sqlite_{role_prefix}_{r[id_col]}"
                data = {
                    "uid": uid, "email": r["email"],
                    "role": role_prefix, "source": "sqlite_sync",
                }
                if name_col:
                    data["name"] = r[name_col]
                if extra and extra in r:
                    data[extra] = r[extra]
                db.collection("users").document(uid).set(data)
                results["users"] += 1

        # ── Sync Quizzes ──
        quizzes = [dict(r) for r in cursor.execute("SELECT * FROM quizzes").fetchall()]
        for q in quizzes:
            qid = f"sqlite_{q['quiz_id']}"
            doc_ref = db.collection("quizzes").document(qid)
            doc_ref.set({
                "quizId": qid, "subject": q["subject"], "topic": q["topic"],
                "createdBy": str(q["created_by"]), "createdByType": q["created_by_type"],
                "difficulty": q["difficulty"], "status": q["status"],
                "totalQuestions": 0, "source": "sqlite_sync",
            })
            results["quizzes"] += 1

        # ── Sync Questions ──
        questions = [dict(r) for r in cursor.execute("SELECT * FROM questions").fetchall()]
        for i, q in enumerate(questions):
            qid = f"sqlite_{q['quiz_id']}_q{i}"
            opts = [q["option_a"], q["option_b"], q["option_c"], q["option_d"]]
            doc_ref = db.collection("questions").document(qid)
            doc_ref.set({
                "questionId": qid, "quizId": f"sqlite_{q['quiz_id']}",
                "question": q["question_text"], "options": opts,
                "correctAnswer": q["correct_answer"], "difficulty": q["difficulty"],
                "explanation": q.get("explanation", ""), "source": "sqlite_sync",
            })
            results["questions"] += 1

        # Update quiz totalQuestions
        for q in quizzes:
            qid = f"sqlite_{q['quiz_id']}"
            qcount = cursor.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (q["quiz_id"],)).fetchone()[0]
            db.collection("quizzes").document(qid).update({"totalQuestions": qcount})

        # ── Sync Quiz Results ──
        quiz_results = [dict(r) for r in cursor.execute("SELECT * FROM quiz_results").fetchall()]
        for r in quiz_results:
            rid = f"sqlite_{r['result_id']}"
            doc_ref = db.collection("quizResults").document(rid)
            doc_ref.set({
                "resultId": rid, "studentId": f"sqlite_student_{r['student_id']}",
                "quizId": f"sqlite_{r['quiz_id']}", "marks": r["marks"],
                "totalQuestions": r["total_questions"], "accuracy": r["accuracy"],
                "timeTaken": r["time_taken"], "difficulty": r["difficulty"],
                "status": r["status"], "topic": r["topic"],
                "date": r["date"], "source": "sqlite_sync",
            })
            results["quizResults"] += 1

        # ── Sync Violations ──
        violations = [dict(r) for r in cursor.execute("SELECT * FROM violations").fetchall()]
        for v in violations:
            vid = f"sqlite_{v['violation_id']}"
            doc_ref = db.collection("violations").document(vid)
            doc_ref.set({
                "violationId": vid, "studentId": f"sqlite_student_{v['student_id']}",
                "quizId": f"sqlite_{v['quiz_id']}", "warningCount": v["warning_count"],
                "source": v.get("source", ""), "date": v["date"], "syncSource": "sqlite_sync",
            })
            results["violations"] += 1

        # ── Sync Streaks ──
        streaks = [dict(r) for r in cursor.execute("SELECT * FROM student_streaks").fetchall()]
        for s in streaks:
            sid = f"sqlite_streak_{s['student_id']}"
            db.collection("streaks").document(sid).set({
                "streakId": sid,
                "studentId": f"sqlite_student_{s['student_id']}",
                "currentStreak": s["current_streak"],
                "longestStreak": s["longest_streak"],
                "lastQuizDate": s["last_quiz_date"] or "",
                "source": "sqlite_sync",
            })
            results.get("streaks", results.setdefault("streaks", 0))
            results["streaks"] = results.get("streaks", 0) + 1

        # ── Sync Badges ──
        badges = [dict(r) for r in cursor.execute("SELECT * FROM badges").fetchall()]
        for b in badges:
            bid = f"sqlite_badge_{b['badge_id']}"
            db.collection("badges").document(bid).set({
                "badgeId": bid,
                "studentId": f"sqlite_student_{b['student_id']}",
                "mentorId": f"sqlite_mentor_{b['mentor_id']}",
                "badgeName": b["badge_name"],
                "badgeIcon": b["badge_icon"],
                "description": b.get("description", ""),
                "createdAt": b["created_at"],
                "source": "sqlite_sync",
            })
            results["badges"] = results.get("badges", 0) + 1

        # ── Sync Feedback ──
        feedback_rows = [dict(r) for r in cursor.execute("SELECT * FROM feedback").fetchall()]
        for fb in feedback_rows:
            fid = f"sqlite_feedback_{fb['feedback_id']}"
            db.collection("feedback").document(fid).set({
                "feedbackId": fid,
                "studentId": f"sqlite_student_{fb['student_id']}",
                "mentorId": f"sqlite_mentor_{fb['mentor_id']}",
                "rating": fb["rating"],
                "comment": fb.get("comment", ""),
                "createdAt": fb["created_at"],
                "source": "sqlite_sync",
            })
            results["feedback"] = results.get("feedback", 0) + 1

        conn.close()
        print(f"[Firebase Sync] Complete: {results}")
        return {"success": True, "results": results}

    except Exception as e:
        conn.close()
        print(f"[Firebase Sync] Error: {e}")
        return {"success": False, "message": str(e)}
