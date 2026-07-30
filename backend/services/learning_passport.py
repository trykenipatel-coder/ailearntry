"""Adaptive Learning Passport — digital learning profile that auto-updates."""
import sys, os, sqlite3, json
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db


class LearningPassport:
    def get_or_create(self, student_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            student = conn.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
            if not student:
                return None

            passport = conn.execute(
                "SELECT * FROM learning_passports WHERE student_id=?", (student_id,)
            ).fetchone()

            results = conn.execute(
                "SELECT accuracy FROM quiz_results WHERE student_id=?", (student_id,)
            ).fetchall()
            attempts = conn.execute(
                "SELECT is_correct, response_time, topic FROM question_attempts WHERE student_id=?", (student_id,)
            ).fetchall()
            mastery = conn.execute(
                "SELECT topic, mastery_pct FROM topic_mastery WHERE student_id=?", (student_id,)
            ).fetchall()
            badges = conn.execute(
                "SELECT COUNT(*) as cnt FROM badges WHERE student_id=?", (student_id,)
            ).fetchone()
            streak = conn.execute(
                "SELECT * FROM student_streaks WHERE student_id=?", (student_id,)
            ).fetchone()

            scores = [r["accuracy"] for r in results] if results else [0]
            avg_accuracy = round(sum(scores) / len(scores), 1) if scores else 0

            total_attempts = len(attempts)
            correct = sum(1 for a in attempts if a["is_correct"])
            overall_acc = round((correct / max(total_attempts, 1)) * 100, 1)

            times = [a["response_time"] for a in attempts if a["response_time"]]
            avg_time = round(sum(times) / len(times), 1) if times else 0

            strong = [{"topic": m["topic"], "mastery": round(m["mastery_pct"], 1)} for m in mastery if m["mastery_pct"] >= 70]
            weak = [{"topic": m["topic"], "mastery": round(m["mastery_pct"], 1)} for m in mastery if m["mastery_pct"] < 50]
            strong.sort(key=lambda x: x["mastery"], reverse=True)
            weak.sort(key=lambda x: x["mastery"])

            avg_mastery = round(sum(m["mastery_pct"] for m in mastery) / max(len(mastery), 1), 1)

            als = min(100, max(0, overall_acc * 0.4 + (100 - min(avg_time * 2, 100)) * 0.3 + avg_mastery * 0.3))

            if als >= 75:
                level = "Advanced"
            elif als >= 45:
                level = "Intermediate"
            else:
                level = "Beginner"

            health = min(100, max(0, avg_accuracy * 0.35 + avg_mastery * 0.35 + (100 - min(avg_time * 1.5, 100)) * 0.2 + (streak["current_streak"] * 5 if streak else 0) * 0.1))

            total_achievements = badges["cnt"] if badges else 0
            current_streak = streak["current_streak"] if streak else 0

            mastery_dict = {m["topic"]: round(m["mastery_pct"], 1) for m in mastery}

            timeline = []
            dates = conn.execute(
                "SELECT date, accuracy FROM quiz_results WHERE student_id=? ORDER BY date ASC", (student_id,)
            ).fetchall()
            for d in dates:
                timeline.append({"date": d["date"][:10] if d["date"] else "", "accuracy": d["accuracy"]})

            recs = []
            if weak:
                recs.append(f"Focus on weak topics: {', '.join(w['topic'] for w in weak[:3])}")
            if avg_time > 45:
                recs.append("Practice timed quizzes to improve speed")
            if total_achievements < 3:
                recs.append("Complete more quizzes to earn achievements")
            if not recs:
                recs.append("Excellent progress! Keep up the momentum")

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if passport:
                conn.execute(
                    """UPDATE learning_passports SET learning_level=?, health_score=?,
                       total_achievements=?, quiz_accuracy=?, avg_response_time=?,
                       revision_streak=?, topic_mastery_json=?, progress_timeline=?,
                       last_updated=? WHERE student_id=?""",
                    (level, round(health, 1), total_achievements, overall_acc, avg_time,
                     current_streak, json.dumps(mastery_dict), json.dumps(timeline), now, student_id)
                )
            else:
                conn.execute(
                    """INSERT INTO learning_passports
                       (student_id, learning_level, health_score, total_achievements,
                        quiz_accuracy, avg_response_time, revision_streak,
                        topic_mastery_json, progress_timeline, last_updated)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (student_id, level, round(health, 1), total_achievements, overall_acc,
                     avg_time, current_streak, json.dumps(mastery_dict), json.dumps(timeline), now)
                )
            conn.commit()

            return {
                "student_name": student["name"],
                "student_code": student["student_code"],
                "course": student["course"],
                "learning_level": level,
                "health_score": round(health, 1),
                "als_score": round(als, 1),
                "quiz_accuracy": overall_acc,
                "avg_response_time": avg_time,
                "total_quizzes": len(results),
                "total_achievements": total_achievements,
                "revision_streak": current_streak,
                "strong_topics": strong[:5],
                "weak_topics": weak[:5],
                "topic_mastery": mastery_dict,
                "progress_timeline": timeline,
                "recommendations": recs,
                "last_updated": now,
            }
        except Exception as e:
            print(f"[LearningPassport] Error: {e}")
            return None
        finally:
            conn.close()
