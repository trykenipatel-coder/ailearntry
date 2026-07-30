"""Mentor Analytics Dashboard — monitors all student progress from one place."""
import sys, os, sqlite3, json
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db


class MentorAnalytics:
    def get_dashboard(self, mentor_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            students = conn.execute("SELECT student_id, name, email, student_code FROM students").fetchall()
            total_students = len(students)

            student_data = []
            for s in students:
                sid = s["student_id"]
                results = conn.execute(
                    "SELECT accuracy, quiz_id, date FROM quiz_results WHERE student_id=? ORDER BY date DESC",
                    (sid,)
                ).fetchall()
                attempts = conn.execute(
                    "SELECT is_correct, response_time, topic FROM question_attempts WHERE student_id=?", (sid,)
                ).fetchall()
                mastery = conn.execute(
                    "SELECT topic, mastery_pct FROM topic_mastery WHERE student_id=?", (sid,)
                ).fetchall()
                streak = conn.execute(
                    "SELECT current_streak FROM student_streaks WHERE student_id=?", (sid,)
                ).fetchone()

                scores = [r["accuracy"] for r in results] if results else [0]
                avg_acc = round(sum(scores) / len(scores), 1) if scores else 0
                total_q = len(results)
                times = [a["response_time"] for a in attempts if a["response_time"]]
                avg_time = round(sum(times) / len(times), 1) if times else 0

                weak = [m["topic"] for m in mastery if m["mastery_pct"] < 50][:3]
                strong = [m["topic"] for m in mastery if m["mastery_pct"] >= 70][:3]

                student_data.append({
                    "student_id": sid,
                    "name": s["name"],
                    "email": s["email"],
                    "student_code": s["student_code"],
                    "total_quizzes": total_q,
                    "avg_accuracy": avg_acc,
                    "avg_response_time": avg_time,
                    "weak_topics": weak,
                    "strong_topics": strong,
                    "current_streak": streak["current_streak"] if streak else 0,
                    "needs_support": avg_acc < 40 and total_q > 0,
                    "is_top": avg_acc >= 80 and total_q >= 3,
                })

            student_data.sort(key=lambda x: x["avg_accuracy"], reverse=True)

            all_topics = {}
            for s in students:
                rows = conn.execute(
                    "SELECT topic, mastery_pct FROM topic_mastery WHERE student_id=?", (s["student_id"],)
                ).fetchall()
                for r in rows:
                    if r["topic"] not in all_topics:
                        all_topics[r["topic"]] = []
                    all_topics[r["topic"]].append(r["mastery_pct"])

            topic_analysis = []
            for topic, pcts in all_topics.items():
                avg = round(sum(pcts) / len(pcts), 1) if pcts else 0
                topic_analysis.append({"topic": topic, "avg_mastery": avg, "student_count": len(pcts)})
            topic_analysis.sort(key=lambda x: x["avg_mastery"])

            total_quizzes_all = sum(s["total_quizzes"] for s in student_data)
            avg_class = round(sum(s["avg_accuracy"] for s in student_data) / max(total_students, 1), 1)
            struggling = [s for s in student_data if s["needs_support"]]
            top = [s for s in student_data if s["is_top"]][:5]
            difficult = [t for t in topic_analysis if t["avg_mastery"] < 50][:5]

            all_results_count = conn.execute("SELECT COUNT(*) as cnt FROM quiz_results").fetchone()["cnt"]
            recent_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            recent_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM quiz_results WHERE date>=?", (recent_date,)
            ).fetchone()["cnt"]
            completion_rate = round((recent_count / max(all_results_count, 1)) * 100, 1)

            return {
                "total_students": total_students,
                "avg_class_performance": avg_class,
                "total_quizzes_taken": total_quizzes_all,
                "quiz_completion_rate": completion_rate,
                "students": student_data,
                "struggling_students": struggling,
                "top_students": top,
                "difficult_topics": difficult,
                "topic_analysis": topic_analysis,
            }
        except Exception as e:
            print(f"[MentorAnalytics] Error: {e}")
            return {"total_students": 0, "avg_class_performance": 0, "students": [], "struggling_students": [], "top_students": [], "difficult_topics": [], "topic_analysis": []}
        finally:
            conn.close()
