"""Semester Learning Report — generates comprehensive student report."""
import sys, os, sqlite3, json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db


class SemesterReport:
    def generate(self, student_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            student = conn.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
            if not student:
                return None

            results = conn.execute(
                "SELECT * FROM quiz_results WHERE student_id=? ORDER BY date DESC", (student_id,)
            ).fetchall()

            attempts = conn.execute(
                "SELECT is_correct, response_time, topic FROM question_attempts WHERE student_id=?", (student_id,)
            ).fetchall()

            mastery = conn.execute(
                "SELECT topic, mastery_pct, total_attempts, correct_count FROM topic_mastery WHERE student_id=?",
                (student_id,)
            ).fetchall()

            badges = conn.execute(
                "SELECT badge_name, badge_icon, description FROM badges WHERE student_id=?", (student_id,)
            ).fetchall()

            streak = conn.execute(
                "SELECT * FROM student_streaks WHERE student_id=?", (student_id,)
            ).fetchone()

            total_quizzes = len(results)
            scores = [r["accuracy"] for r in results] if results else [0]
            avg_score = round(sum(scores) / len(scores), 1) if scores else 0

            total_attempts_count = len(attempts)
            correct_attempts = sum(1 for a in attempts if a["is_correct"])
            overall_accuracy = round((correct_attempts / max(total_attempts_count, 1)) * 100, 1)

            times = [a["response_time"] for a in attempts if a["response_time"]]
            avg_time = round(sum(times) / len(times), 1) if times else 0
            total_time = sum(times) if times else 0

            topic_list = []
            for m in mastery:
                topic_list.append({
                    "topic": m["topic"],
                    "mastery_pct": round(m["mastery_pct"], 1),
                    "total_attempts": m["total_attempts"],
                    "correct_count": m["correct_count"],
                })
            topic_list.sort(key=lambda x: x["mastery_pct"], reverse=True)

            strong = [t for t in topic_list if t["mastery_pct"] >= 70][:5]
            weak = [t for t in topic_list if t["mastery_pct"] < 50][:5]

            als = 50
            if attempts:
                als = min(100, max(0, overall_accuracy * 0.4 + (100 - min(avg_time * 2, 100)) * 0.3 + (len(topic_list) * 5) * 0.3))

            improvement = 0
            if len(results) >= 2:
                recent = results[0]["accuracy"]
                older = results[-1]["accuracy"]
                improvement = round(recent - older, 1)

            recs = []
            for w in weak[:3]:
                recs.append(f"Focus on improving {w['topic']} — currently at {w['mastery_pct']}% mastery")
            if avg_time > 40:
                recs.append("Work on response speed — practice timed quizzes")
            if total_quizzes < 5:
                recs.append("Attempt more quizzes to strengthen your profile")
            if not recs:
                recs.append("Great progress! Keep maintaining your current pace")

            achievement_list = [{"name": b["badge_name"], "icon": b["badge_icon"], "desc": b["description"]} for b in badges]

            timeline = []
            for r in reversed(results):
                timeline.append({"date": r["date"][:10] if r["date"] else "", "accuracy": r["accuracy"]})

            report = {
                "student_name": student["name"],
                "student_code": student["student_code"],
                "course": student["course"],
                "semester": "Current Semester",
                "total_quizzes": total_quizzes,
                "avg_score": avg_score,
                "overall_accuracy": overall_accuracy,
                "als_score": round(als, 1),
                "total_time_hours": round(total_time / 3600, 2),
                "avg_response_time": avg_time,
                "total_questions_attempted": total_attempts_count,
                "topic_mastery": topic_list,
                "strong_topics": strong,
                "weak_topics": weak,
                "achievements": achievement_list,
                "streak_current": streak["current_streak"] if streak else 0,
                "streak_longest": streak["longest_streak"] if streak else 0,
                "improvement_pct": improvement,
                "recommendations": recs,
                "progress_timeline": timeline,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            return report
        except Exception as e:
            print(f"[SemesterReport] Error: {e}")
            return None
        finally:
            conn.close()
