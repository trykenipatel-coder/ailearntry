"""
Explainable Recommendation Engine (ERE)
========================================
Provides transparent, rule-based learning recommendations
with human-readable explanations derived from student performance metrics.

Rules:
  Rule 1: Accuracy < 50%        -> Recommend Revision
  Rule 2: Average Time > 60 sec -> More Practice (Speed)
  Rule 3: Wrong Attempts > 5    -> Practice Quiz
  Rule 4: Mastery > 90%         -> Skip Revision
  Rule 5: 3 Consecutive Wrong   -> Easy Level Questions
"""

import sys
import os
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db


class RecommendationEngine:
    """Generates explainable learning recommendations."""

    def generate_recommendations(self, student_id):
        """Generate all recommendations for a student."""
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            topics = conn.execute(
                "SELECT topic, total_attempts, correct_count, avg_response_time, mastery_pct "
                "FROM topic_mastery WHERE student_id=? AND total_attempts > 0",
                (student_id,)
            ).fetchall()

            if not topics:
                return {"recommendations": [], "summary": {"total": 0, "high": 0, "medium": 0, "low": 0}}

            all_recs = []
            for t in topics:
                recs = self._analyze_topic(student_id, t, conn)
                all_recs.extend(recs)

            all_recs.sort(key=lambda x: {"High": 3, "Medium": 2, "Low": 1}.get(x["priority"], 0), reverse=True)

            self._save_recommendations(student_id, all_recs)

            summary = {
                "total": len(all_recs),
                "high": sum(1 for r in all_recs if r["priority"] == "High"),
                "medium": sum(1 for r in all_recs if r["priority"] == "Medium"),
                "low": sum(1 for r in all_recs if r["priority"] == "Low"),
            }

            return {"recommendations": all_recs, "summary": summary}

        except Exception as e:
            print(f"[ERE] Error generating recommendations: {e}")
            return {"recommendations": [], "summary": {"total": 0, "high": 0, "medium": 0, "low": 0}}
        finally:
            conn.close()

    def _analyze_topic(self, student_id, topic_row, conn):
        """Apply all rules to a single topic and return recommendations."""
        topic = topic_row["topic"]
        total = topic_row["total_attempts"]
        correct = topic_row["correct_count"]
        avg_time = topic_row["avg_response_time"] or 30
        mastery = topic_row["mastery_pct"] or 0

        accuracy = (correct / max(total, 1)) * 100
        wrong_count = total - correct

        recent = conn.execute(
            "SELECT is_correct FROM question_attempts WHERE student_id=? AND topic=? "
            "ORDER BY created_at DESC LIMIT 3",
            (student_id, topic)
        ).fetchall()
        consecutive_wrong = 0
        for r in recent:
            if r["is_correct"] == 0:
                consecutive_wrong += 1
            else:
                break

        recs = []

        if mastery > 90:
            recs.append(self._build_rec(
                topic, "Skip Revision", "Low",
                [f"Mastery at {mastery:.0f}% (excellent)", "No immediate revision needed"],
                accuracy, mastery, avg_time, wrong_count, confidence="High", est_min=0
            ))
            return recs

        if accuracy < 50:
            reasons = [f"Accuracy only {accuracy:.0f}%", f"Mastery at {mastery:.0f}%"]
            if wrong_count > 5:
                reasons.append(f"{wrong_count} wrong attempts recorded")
            recs.append(self._build_rec(
                topic, "Study Topic", "High", reasons,
                accuracy, mastery, avg_time, wrong_count, confidence="High", est_min=25
            ))

        if avg_time > 60:
            reasons = [f"Avg response time {avg_time:.0f}s (slow)", "Needs timed practice"]
            if accuracy < 60:
                reasons.append("Low accuracy compounds speed issue")
            recs.append(self._build_rec(
                topic, "Timed Practice", "High" if accuracy < 50 else "Medium", reasons,
                accuracy, mastery, avg_time, wrong_count, confidence="Medium", est_min=20
            ))

        if wrong_count > 5:
            reasons = [f"{wrong_count} wrong attempts", "Focused practice recommended"]
            if mastery < 50:
                reasons.append(f"Mastery at {mastery:.0f}% needs improvement")
            recs.append(self._build_rec(
                topic, "Practice Quiz", "Medium", reasons,
                accuracy, mastery, avg_time, wrong_count, confidence="Medium", est_min=15
            ))

        if consecutive_wrong >= 3:
            recs.append(self._build_rec(
                topic, "Easy Questions", "High",
                [f"{consecutive_wrong} consecutive wrong answers", "Start with easier questions to build confidence"],
                accuracy, mastery, avg_time, wrong_count, confidence="High", est_min=20
            ))

        if mastery >= 40 and mastery <= 90 and accuracy >= 50 and accuracy < 80 and avg_time <= 60:
            recs.append(self._build_rec(
                topic, "Practice Medium Questions", "Low",
                [f"Accuracy {accuracy:.0f}% (good but can improve)", f"Mastery {mastery:.0f}% (improving)", "Speed is acceptable"],
                accuracy, mastery, avg_time, wrong_count, confidence="Medium", est_min=15
            ))

        if not recs:
            recs.append(self._build_rec(
                topic, "Continue Current Pace", "Low",
                [f"Accuracy {accuracy:.0f}%", f"Mastery {mastery:.0f}%", "Performance is stable"],
                accuracy, mastery, avg_time, wrong_count, confidence="Low", est_min=10
            ))

        return recs

    def _build_rec(self, topic, rec_type, priority, reasons, accuracy, mastery, avg_time, wrong_count, confidence="Medium", est_min=15):
        return {
            "topic": topic,
            "recommendation_type": rec_type,
            "priority": priority,
            "reasons": reasons,
            "reason_text": " | ".join(reasons),
            "confidence": confidence,
            "accuracy": round(accuracy, 1),
            "mastery": round(mastery, 1),
            "avg_time": round(avg_time, 1),
            "wrong_attempts": wrong_count,
            "estimated_minutes": est_min,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _save_recommendations(self, student_id, recs):
        conn = get_db()
        try:
            conn.execute(
                "UPDATE recommendations SET status='dismissed' WHERE student_id=? AND status='active'",
                (student_id,)
            )
            for r in recs:
                conn.execute(
                    """INSERT INTO recommendations
                       (student_id, topic, recommendation_type, priority, reason, confidence,
                        accuracy_snapshot, mastery_snapshot, avg_time_snapshot, wrong_attempts_snapshot,
                        estimated_minutes, status, generated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
                    (student_id, r["topic"], r["recommendation_type"], r["priority"],
                     r["reason_text"], r["confidence"], r["accuracy"], r["mastery"],
                     r["avg_time"], r["wrong_attempts"], r["estimated_minutes"], r["generated_at"])
                )
            conn.commit()
        except Exception as e:
            print(f"[ERE] Error saving recommendations: {e}")
        finally:
            conn.close()

    def get_active_recommendations(self, student_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM recommendations WHERE student_id=? AND status='active' "
                "ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END",
                (student_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[ERE] Error getting recommendations: {e}")
            return []
        finally:
            conn.close()
