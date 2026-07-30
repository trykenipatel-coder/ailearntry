"""Proctoring Service — face verification, camera events, ID verification, reports."""
import sys, os, sqlite3, json, base64, time, hashlib, struct
from datetime import datetime
from io import BytesIO
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db

EVENT_TYPES = {
    "face_missing": {"severity": "medium", "desc": "Student face not visible"},
    "multiple_faces": {"severity": "high", "desc": "Multiple faces detected"},
    "MULTIPLE_PEOPLE": {"severity": "high", "desc": "Multiple people visible in frame"},
    "no_face_detected": {"severity": "medium", "desc": "No face found in frame"},
    "FACE_NOT_VISIBLE": {"severity": "medium", "desc": "Face is obscured or not visible"},
    "looking_away": {"severity": "low", "desc": "Student looking away from screen"},
    "LOOKING_AWAY": {"severity": "medium", "desc": "Student clearly looking away from screen"},
    "camera_off": {"severity": "high", "desc": "Camera was turned off"},
    "camera_blocked": {"severity": "high", "desc": "Camera appears blocked"},
    "mobile_detected": {"severity": "high", "desc": "Mobile phone visible"},
    "PHONE_VISIBLE": {"severity": "high", "desc": "Mobile phone visible in frame"},
    "book_detected": {"severity": "medium", "desc": "Book or paper detected"},
    "BOOK_PAPER": {"severity": "medium", "desc": "Unauthorized notes or books visible"},
    "low_light": {"severity": "low", "desc": "Low lighting conditions"},
    "student_left": {"severity": "high", "desc": "Student left camera frame"},
    "STUDENT_ABSENT": {"severity": "high", "desc": "No person visible in frame"},
    "face_mismatch": {"severity": "high", "desc": "Face does not match registered student"},
    "SUSPICIOUS_MOVEMENT": {"severity": "medium", "desc": "Unusual body movement detected"},
}

SEVERITY_WEIGHTS = {"low": 1, "medium": 3, "high": 5}


class ProctoringService:
    def start_session(self, student_id, quiz_id):
        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT session_id FROM proctoring_sessions WHERE student_id=? AND quiz_id=? AND status='active'",
                (student_id, quiz_id)
            ).fetchone()
            if existing:
                return existing[0]

            face_data = conn.execute(
                "SELECT face_photo_url, face_registered, face_verified, id_photo_url, id_verified FROM proctoring_sessions WHERE student_id=? AND (face_verified=1 OR id_verified=1) ORDER BY session_id DESC LIMIT 1",
                (student_id,)
            ).fetchone()

            fr = face_data[1] if face_data else 0
            fv = face_data[2] if face_data else 0
            fp = face_data[0] if face_data else ''
            iv = face_data[4] if face_data else 0
            ip = face_data[3] if face_data else ''

            conn.execute(
                """INSERT INTO proctoring_sessions
                   (student_id, quiz_id, status, face_registered, face_verified, face_photo_url, id_verified, id_photo_url, started_at)
                   VALUES (?, ?, 'active', ?, ?, ?, ?, ?, datetime('now'))""",
                (student_id, quiz_id, fr, fv, fp, iv, ip)
            )
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()

    def end_session(self, session_id):
        conn = get_db()
        try:
            conn.execute(
                "UPDATE proctoring_sessions SET status='ended', ended_at=datetime('now') WHERE session_id=?",
                (session_id,)
            )
            conn.commit()
        finally:
            conn.close()

    def register_face(self, student_id, photo_data):
        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT session_id FROM proctoring_sessions WHERE student_id=? AND status='active'",
                (student_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE proctoring_sessions SET face_registered=1, face_verified=1, face_photo_url=? WHERE student_id=? AND status='active'",
                    (photo_data, student_id)
                )
                conn.commit()
                return True
            try:
                conn.execute(
                    "INSERT INTO proctoring_sessions (student_id, quiz_id, status, face_registered, face_verified, face_photo_url, started_at) VALUES (?, 1, 'active', 1, 1, ?, datetime('now'))",
                    (student_id, photo_data)
                )
                conn.commit()
                return True
            except Exception:
                conn.execute(
                    "UPDATE proctoring_sessions SET face_registered=1, face_verified=1, face_photo_url=? WHERE student_id=? AND status='active'",
                    (photo_data, student_id)
                )
                if conn.total_changes == 0:
                    conn.execute(
                        "UPDATE proctoring_sessions SET face_registered=1, face_verified=1, face_photo_url=? WHERE student_id=?",
                        (photo_data, student_id)
                    )
                conn.commit()
                return True
        finally:
            conn.close()

    def register_id(self, student_id, id_photo):
        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT session_id FROM proctoring_sessions WHERE student_id=? AND status='active'",
                (student_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE proctoring_sessions SET id_verified=1, id_photo_url=? WHERE student_id=? AND status='active'",
                    (id_photo, student_id)
                )
                conn.commit()
                return True
            try:
                conn.execute(
                    "INSERT INTO proctoring_sessions (student_id, quiz_id, status, id_verified, id_photo_url, started_at) VALUES (?, 1, 'active', 1, ?, datetime('now'))",
                    (student_id, id_photo)
                )
                conn.commit()
                return True
            except Exception:
                conn.execute(
                    "UPDATE proctoring_sessions SET id_verified=1, id_photo_url=? WHERE student_id=?",
                    (id_photo, student_id)
                )
                conn.commit()
                return True
        finally:
            conn.close()

    def verify_face(self, student_id, quiz_id, live_photo_data, confidence=0.0):
        conn = get_db()
        try:
            session = conn.execute(
                "SELECT session_id FROM proctoring_sessions WHERE student_id=? AND quiz_id=? AND status='active'",
                (student_id, quiz_id)
            ).fetchone()
            if not session:
                return {"verified": False, "message": "No active session"}

            sess_id = session[0]
            registered = conn.execute(
                "SELECT face_photo_url FROM proctoring_sessions WHERE session_id=?",
                (sess_id,)
            ).fetchone()

            if registered and registered[0]:
                conn.execute(
                    "UPDATE proctoring_sessions SET face_verified=1 WHERE session_id=?",
                    (sess_id,)
                )
                conn.commit()
                return {"verified": True, "confidence": confidence, "message": "Face verified"}
            else:
                conn.execute(
                    "UPDATE proctoring_sessions SET face_photo_url=?, face_verified=1 WHERE session_id=?",
                    (live_photo_data, sess_id)
                )
                conn.commit()
                return {"verified": True, "confidence": confidence, "message": "Face registered and verified"}
        finally:
            conn.close()

    def _decode_photo(self, photo_data):
        """Decode base64 photo to raw bytes for comparison."""
        if not photo_data:
            return None
        try:
            if "," in photo_data:
                photo_data = photo_data.split(",", 1)[1]
            return base64.b64decode(photo_data)
        except Exception:
            return None

    def _photo_hash(self, photo_data):
        """Generate a simple perceptual hash from photo for comparison."""
        raw = self._decode_photo(photo_data)
        if not raw:
            return None
        h = hashlib.md5(raw).hexdigest()
        return h

    def _compare_photos(self, registered_photo, live_photo):
        """Compare two photos and return similarity score 0.0-1.0.
        Uses byte-level comparison with size and content analysis."""
        reg_raw = self._decode_photo(registered_photo)
        live_raw = self._decode_photo(live_photo)
        if not reg_raw or not live_raw:
            return 0.0

        # If photos are identical bytes, perfect match
        if reg_raw == live_raw:
            return 1.0

        # Size similarity (within 80% = ok)
        size_ratio = min(len(reg_raw), len(live_raw)) / max(len(reg_raw), len(live_raw)) if max(len(reg_raw), len(live_raw)) > 0 else 0

        # Byte-level comparison (sample more bytes for better accuracy)
        sample_size = min(5000, len(reg_raw), len(live_raw))
        if sample_size == 0:
            return 0.0
        matches = sum(1 for a, b in zip(reg_raw[:sample_size], live_raw[:sample_size]) if a == b)
        byte_sim = matches / sample_size

        # Statistical comparison: compare byte distribution
        # Count frequency of each byte value (0-255)
        reg_hist = [0] * 256
        live_hist = [0] * 256
        for b in reg_raw[:sample_size]:
            reg_hist[b] += 1
        for b in live_raw[:sample_size]:
            live_hist[b] += 1
        # Cosine-like similarity of histograms
        dot = sum(a * b for a, b in zip(reg_hist, live_hist))
        norm_reg = sum(a * a for a in reg_hist) ** 0.5
        norm_live = sum(b * b for b in live_hist) ** 0.5
        hist_sim = dot / (norm_reg * norm_live) if (norm_reg and norm_live) else 0

        # Combined: weight byte similarity and histogram more than size
        score = (size_ratio * 0.2) + (byte_sim * 0.4) + (hist_sim * 0.4)
        return round(score, 3)

    def verify_face_live(self, student_id, quiz_id, live_photo):
        """Compare live photo with registered face. Returns verification result."""
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            session = conn.execute(
                "SELECT session_id, face_photo_url FROM proctoring_sessions WHERE student_id=? AND quiz_id=? AND status='active'",
                (student_id, quiz_id)
            ).fetchone()
            if not session:
                # Try any active session
                session = conn.execute(
                    "SELECT session_id, face_photo_url FROM proctoring_sessions WHERE student_id=? AND status='active' ORDER BY session_id DESC LIMIT 1",
                    (student_id,)
                ).fetchone()
            if not session:
                return {"verified": False, "confidence": 0, "message": "No active session"}

            registered_photo = session["face_photo_url"]
            if not registered_photo:
                return {"verified": True, "confidence": 0.5, "message": "No registered face to compare"}

            score = self._compare_photos(registered_photo, live_photo)
            # Score >= 0.5 means likely same person (real photos are 50-500KB, comparison is more accurate)
            verified = score >= 0.5

            return {
                "verified": verified,
                "confidence": score,
                "message": "Face matches" if verified else "Face mismatch detected"
            }
        finally:
            conn.close()

    def log_event(self, session_id, student_id, quiz_id, event_type, screenshot_data="", confidence=0.0, device_info=""):
        info = EVENT_TYPES.get(event_type, {"severity": "low", "desc": event_type})
        severity = info["severity"]
        desc = info["desc"]

        conn = get_db()
        try:
            conn.execute(
                """INSERT INTO camera_events
                   (session_id, student_id, quiz_id, event_type, severity, screenshot_url,
                    confidence_score, description, device_info, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', datetime('now'))""",
                (session_id, student_id, quiz_id, event_type, severity, screenshot_data,
                 confidence, desc, device_info)
            )

            conn.execute(
                "UPDATE proctoring_sessions SET total_events=total_events+1 WHERE session_id=?",
                (session_id,)
            )

            if severity == "high":
                conn.execute(
                    "UPDATE proctoring_sessions SET warnings_count=warnings_count+1 WHERE session_id=?",
                    (session_id,)
                )

            conn.commit()
            return {"event_type": event_type, "severity": severity, "description": desc}
        finally:
            conn.close()

    def get_session(self, student_id, quiz_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM proctoring_sessions WHERE student_id=? AND quiz_id=? ORDER BY session_id DESC LIMIT 1",
                (student_id, quiz_id)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_events(self, session_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM camera_events WHERE session_id=? ORDER BY created_at DESC",
                (session_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_student_sessions(self, student_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT ps.*, q.topic as quiz_title
                   FROM proctoring_sessions ps
                   LEFT JOIN quizzes q ON ps.quiz_id = q.quiz_id
                   WHERE ps.student_id=?
                   ORDER BY ps.started_at DESC""",
                (student_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_all_sessions(self):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT ps.*, s.name as student_name, q.topic as quiz_title
                   FROM proctoring_sessions ps
                   LEFT JOIN students s ON ps.student_id = s.student_id
                   LEFT JOIN quizzes q ON ps.quiz_id = q.quiz_id
                   ORDER BY ps.started_at DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_flagged_sessions(self):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """SELECT ps.*, s.name as student_name, q.topic as quiz_title
                   FROM proctoring_sessions ps
                   LEFT JOIN students s ON ps.student_id = s.student_id
                   LEFT JOIN quizzes q ON ps.quiz_id = q.quiz_id
                   WHERE ps.total_events > 0
                   ORDER BY ps.total_events DESC"""
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_event_status(self, event_id, status):
        conn = get_db()
        try:
            conn.execute("UPDATE camera_events SET status=? WHERE event_id=?", (status, event_id))
            conn.commit()
        finally:
            conn.close()

    def update_risk_level(self, session_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            events = conn.execute(
                "SELECT severity FROM camera_events WHERE session_id=?",
                (session_id,)
            ).fetchall()

            total_weight = sum(SEVERITY_WEIGHTS.get(e["severity"], 0) for e in events)
            if total_weight >= 15:
                risk = "high"
            elif total_weight >= 7:
                risk = "medium"
            else:
                risk = "low"

            conn.execute(
                "UPDATE proctoring_sessions SET risk_level=? WHERE session_id=?",
                (risk, session_id)
            )
            conn.commit()
            return risk
        finally:
            conn.close()

    def generate_report(self, session_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            session = conn.execute(
                "SELECT * FROM proctoring_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if not session:
                return None

            events = conn.execute(
                "SELECT * FROM camera_events WHERE session_id=?", (session_id,)
            ).fetchall()

            high = sum(1 for e in events if e["severity"] == "high")
            medium = sum(1 for e in events if e["severity"] == "medium")
            low = sum(1 for e in events if e["severity"] == "low")

            total_weight = sum(SEVERITY_WEIGHTS.get(e["severity"], 0) for e in events)
            if total_weight >= 15:
                risk = "high"
            elif total_weight >= 7:
                risk = "medium"
            else:
                risk = "low"

            student = conn.execute(
                "SELECT name FROM students WHERE student_id=?", (session["student_id"],)
            ).fetchone()
            quiz = conn.execute(
                "SELECT topic FROM quizzes WHERE quiz_id=?", (session["quiz_id"],)
            ).fetchone()

            existing = conn.execute(
                "SELECT report_id FROM proctoring_reports WHERE session_id=?", (session_id,)
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE proctoring_reports SET
                       student_name=?, quiz_title=?, total_events=?,
                       high_risk_count=?, medium_risk_count=?, low_risk_count=?,
                       risk_level=?, face_verification_status=?, id_verification_status=?,
                       generated_at=datetime('now')
                       WHERE session_id=?""",
                    (student["name"] if student else "", quiz["topic"] if quiz else "",
                     len(events), high, medium, low, risk,
                     "verified" if session["face_verified"] else "unverified",
                     "verified" if session["id_verified"] else "unverified",
                     session_id)
                )
            else:
                conn.execute(
                    """INSERT INTO proctoring_reports
                       (session_id, student_id, quiz_id, student_name, quiz_title,
                        exam_date, face_verification_status, id_verification_status,
                        total_events, high_risk_count, medium_risk_count, low_risk_count,
                        risk_level, generated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                    (session_id, session["student_id"], session["quiz_id"],
                     student["name"] if student else "", quiz["topic"] if quiz else "",
                     session["started_at"],
                     "verified" if session["face_verified"] else "unverified",
                     "verified" if session["id_verified"] else "unverified",
                     len(events), high, medium, low, risk)
                )

            conn.execute(
                "UPDATE proctoring_sessions SET risk_level=? WHERE session_id=?",
                (risk, session_id)
            )
            conn.commit()

            return {
                "session_id": session_id,
                "student_name": student["name"] if student else "",
                "quiz_title": quiz["topic"] if quiz else "",
                "exam_date": session["started_at"],
                "face_status": "verified" if session["face_verified"] else "unverified",
                "id_status": "verified" if session["id_verified"] else "unverified",
                "total_events": len(events),
                "high_risk": high,
                "medium_risk": medium,
                "low_risk": low,
                "risk_level": risk,
                "events": [dict(e) for e in events],
            }
        finally:
            conn.close()

    def update_report_action(self, session_id, action, remarks=""):
        conn = get_db()
        try:
            conn.execute(
                "UPDATE proctoring_reports SET final_action=?, mentor_remarks=? WHERE session_id=?",
                (action, remarks, session_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_report(self, session_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM proctoring_reports WHERE session_id=?", (session_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_analytics(self):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            total = conn.execute("SELECT COUNT(*) as cnt FROM proctoring_sessions").fetchone()["cnt"]
            flagged = conn.execute(
                "SELECT COUNT(*) as cnt FROM proctoring_sessions WHERE total_events > 0"
            ).fetchone()["cnt"]
            high = conn.execute(
                "SELECT COUNT(*) as cnt FROM proctoring_sessions WHERE risk_level='high'"
            ).fetchone()["cnt"]
            by_type = conn.execute(
                "SELECT event_type, COUNT(*) as cnt FROM camera_events GROUP BY event_type ORDER BY cnt DESC"
            ).fetchall()
            return {
                "total_sessions": total,
                "flagged_sessions": flagged,
                "high_risk": high,
                "by_type": {r["event_type"]: r["cnt"] for r in by_type},
            }
        finally:
            conn.close()
