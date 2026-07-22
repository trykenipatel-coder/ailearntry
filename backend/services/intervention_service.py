"""Intervention Service — auto-detect struggling students, manage interventions."""
import sys, os, sqlite3, json
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db


class InterventionService:
    def detect_struggling_students(self):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            students = conn.execute("SELECT student_id, name, email, student_code FROM students").fetchall()
            struggling = []
            for s in students:
                sid = s["student_id"]
                results = conn.execute(
                    "SELECT accuracy FROM quiz_results WHERE student_id=? ORDER BY date DESC LIMIT 5", (sid,)
                ).fetchall()
                mastery = conn.execute(
                    "SELECT topic, mastery_pct FROM topic_mastery WHERE student_id=?", (sid,)
                ).fetchall()

                if not results:
                    continue

                scores = [r["accuracy"] for r in results]
                avg = round(sum(scores) / len(scores), 1)
                weak = [m["topic"] for m in mastery if m["mastery_pct"] < 50]
                very_weak = [m["topic"] for m in mastery if m["mastery_pct"] < 30]

                reasons = []
                if avg < 40:
                    reasons.append(f"Average score {avg}% — below 40% threshold")
                elif avg < 60:
                    reasons.append(f"Average score {avg}% — below 60% target")

                if len(very_weak) >= 2:
                    reasons.append(f"{len(very_weak)} topics below 30% mastery")
                elif len(weak) >= 3:
                    reasons.append(f"{len(weak)} topics below 50% mastery")

                if len(results) < 3:
                    reasons.append("Low quiz participation — only " + str(len(results)) + " quizzes taken")

                if reasons:
                    priority = "High" if avg < 40 or len(very_weak) >= 2 else "Medium" if avg < 60 else "Low"
                    struggling.append({
                        "student_id": sid,
                        "name": s["name"],
                        "email": s["email"],
                        "student_code": s["student_code"],
                        "avg_accuracy": avg,
                        "quizzes_taken": len(results),
                        "weak_topics": weak[:5],
                        "very_weak_topics": very_weak[:5],
                        "reasons": reasons,
                        "priority": priority,
                    })

            struggling.sort(key=lambda x: x["avg_accuracy"])
            return struggling
        except Exception as e:
            print(f"[InterventionService] detect_struggling error: {e}")
            return []
        finally:
            conn.close()

    def create_intervention(self, mentor_id, student_id, intervention_type, topic, reason, priority, deadline):
        conn = get_db()
        try:
            cursor = conn.execute(
                """INSERT INTO interventions (student_id, mentor_id, intervention_type, topic, reason, priority, status, deadline, assigned_date)
                   VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, datetime('now'))""",
                (student_id, mentor_id, intervention_type, topic, reason, priority, deadline)
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"[InterventionService] create error: {e}")
            return None
        finally:
            conn.close()

    def list_interventions(self, mentor_id=None, student_id=None):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            if mentor_id:
                rows = conn.execute(
                    """SELECT i.*, s.name as student_name, s.student_code
                       FROM interventions i JOIN students s ON i.student_id=s.student_id
                       WHERE i.mentor_id=? ORDER BY i.assigned_date DESC""",
                    (mentor_id,)
                ).fetchall()
            elif student_id:
                rows = conn.execute(
                    """SELECT i.*, m.mentor_name as mentor_name
                       FROM interventions i JOIN mentors m ON i.mentor_id=m.mentor_id
                       WHERE i.student_id=? ORDER BY i.assigned_date DESC""",
                    (student_id,)
                ).fetchall()
            else:
                rows = []

            result = []
            for r in rows:
                result.append({
                    "intervention_id": r["intervention_id"],
                    "student_id": r["student_id"],
                    "student_name": r["student_name"] if "student_name" in r.keys() else "",
                    "student_code": r["student_code"] if "student_code" in r.keys() else "",
                    "mentor_id": r["mentor_id"],
                    "mentor_name": r["mentor_name"] if "mentor_name" in r.keys() else "",
                    "intervention_type": r["intervention_type"],
                    "topic": r["topic"],
                    "reason": r["reason"],
                    "priority": r["priority"],
                    "status": r["status"],
                    "deadline": r["deadline"],
                    "assigned_date": r["assigned_date"],
                    "completion_date": r["completion_date"],
                    "notes": r["notes"],
                })
            return result
        except Exception as e:
            print(f"[InterventionService] list error: {e}")
            return []
        finally:
            conn.close()

    def update_status(self, intervention_id, status, notes=""):
        conn = get_db()
        try:
            completion = ""
            if status == "Completed":
                completion = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE interventions SET status=?, completion_date=?, notes=? WHERE intervention_id=?",
                (status, completion, notes, intervention_id)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[InterventionService] update error: {e}")
            return False
        finally:
            conn.close()

    def get_stats(self, mentor_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            total = conn.execute("SELECT COUNT(*) as cnt FROM interventions WHERE mentor_id=?", (mentor_id,)).fetchone()["cnt"]
            pending = conn.execute("SELECT COUNT(*) as cnt FROM interventions WHERE mentor_id=? AND status='Pending'", (mentor_id,)).fetchone()["cnt"]
            in_progress = conn.execute("SELECT COUNT(*) as cnt FROM interventions WHERE mentor_id=? AND status='In Progress'", (mentor_id,)).fetchone()["cnt"]
            completed = conn.execute("SELECT COUNT(*) as cnt FROM interventions WHERE mentor_id=? AND status='Completed'", (mentor_id,)).fetchone()["cnt"]
            high = conn.execute("SELECT COUNT(*) as cnt FROM interventions WHERE mentor_id=? AND priority='High' AND status!='Completed'", (mentor_id,)).fetchone()["cnt"]

            by_type = {}
            for t in ["Quiz", "Revision", "Material", "Reminder", "Meeting"]:
                cnt = conn.execute("SELECT COUNT(*) as cnt FROM interventions WHERE mentor_id=? AND intervention_type=?", (mentor_id, t)).fetchone()["cnt"]
                by_type[t] = cnt

            return {
                "total": total,
                "pending": pending,
                "in_progress": in_progress,
                "completed": completed,
                "high_priority": high,
                "by_type": by_type,
            }
        except Exception as e:
            print(f"[InterventionService] stats error: {e}")
            return {"total": 0, "pending": 0, "in_progress": 0, "completed": 0, "high_priority": 0, "by_type": {}}
        finally:
            conn.close()
