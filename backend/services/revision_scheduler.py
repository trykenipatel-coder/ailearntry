"""
Personalized Revision Scheduler (PRS)
======================================
Generates dynamic revision timetables using learner performance,
topic mastery, response time, and revision history.

Revision Priority Score Formula:
RPS = (40 x Wrong Attempt Ratio) + (30 x (100 - Mastery))
    + (20 x Response Time Score) + (10 x Days Since Last Revision)

Schedule:
  90-100 -> Today
  75-89  -> Tomorrow
  60-74  -> After 2 Days
  40-59  -> After 5 Days
  Below 40 -> Next Week
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db


class RevisionScheduler:
    """Calculates revision priority and generates revision schedules."""

    SCHEDULE_THRESHOLDS = [
        (90, 0, "Today"),
        (75, 1, "Tomorrow"),
        (60, 2, "After 2 Days"),
        (40, 5, "After 5 Days"),
        (0, 7, "Next Week"),
    ]

    def calculate_rps(self, student_id, topic):
        """
        Calculate Revision Priority Score for a topic.

        RPS = (40 * WrongRatio) + (30 * (100 - Mastery))
            + (20 * TimeScore) + (10 * DaysSinceRevision)

        Returns dict with rps, breakdown, and schedule info.
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            mastery_row = conn.execute(
                "SELECT * FROM topic_mastery WHERE student_id=? AND topic=?",
                (student_id, topic)
            ).fetchone()

            if not mastery_row:
                return self._default_result(topic)

            total_attempts = mastery_row["total_attempts"]
            correct_count = mastery_row["correct_count"]
            avg_response_time = mastery_row["avg_response_time"]
            mastery_pct = mastery_row["mastery_pct"]
            last_attempted = mastery_row["last_attempted"]

            wrong_count = total_attempts - correct_count
            wrong_ratio = (wrong_count / max(total_attempts, 1)) * 100

            time_score = max(0, min(100, (30 / max(avg_response_time, 1)) * 100))

            if last_attempted:
                try:
                    last_date = datetime.strptime(str(last_attempted)[:19], "%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    last_date = datetime.now() - timedelta(days=7)
            else:
                last_date = datetime.now() - timedelta(days=7)
            days_since = (datetime.now() - last_date).days

            rps = (40 * (wrong_ratio / 100)) + (30 * ((100 - mastery_pct) / 100)) + \
                  (20 * (time_score / 100)) + (10 * min(days_since / 7, 1))

            rps = round(min(100, max(0, rps * 100 / 100)), 1)

            schedule_label, days_offset = self._get_schedule(rps)
            next_date = (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")

            return {
                "topic": topic,
                "rps": rps,
                "wrong_ratio": round(wrong_ratio, 1),
                "wrong_count": wrong_count,
                "mastery_pct": round(mastery_pct, 1),
                "avg_response_time": round(avg_response_time, 1),
                "time_score": round(time_score, 1),
                "days_since_revision": days_since,
                "schedule": schedule_label,
                "next_revision_date": next_date,
                "estimated_minutes": self._estimate_time(wrong_count, mastery_pct),
                "breakdown": {
                    "wrong_attempt_score": round(40 * (wrong_ratio / 100), 1),
                    "mastery_score": round(30 * ((100 - mastery_pct) / 100), 1),
                    "time_score": round(20 * (time_score / 100), 1),
                    "recency_score": round(10 * min(days_since / 7, 1), 1),
                }
            }

        except Exception as e:
            print(f"[PRS] Error calculating RPS for {topic}: {e}")
            return self._default_result(topic)
        finally:
            conn.close()

    def generate_schedule(self, student_id):
        """Generate full revision schedule for all topics."""
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            topics = conn.execute(
                "SELECT topic FROM topic_mastery WHERE student_id=? AND total_attempts > 0",
                (student_id,)
            ).fetchall()

            schedule = []
            for row in topics:
                topic = row["topic"]
                rps_data = self.calculate_rps(student_id, topic)
                schedule.append(rps_data)

            schedule.sort(key=lambda x: x["rps"], reverse=True)

            self._save_schedule(student_id, schedule)

            today = [s for s in schedule if s["schedule"] == "Today"]
            tomorrow = [s for s in schedule if s["schedule"] == "Tomorrow"]
            this_week = [s for s in schedule if s["schedule"] in ("After 2 Days", "After 5 Days")]
            next_week = [s for s in schedule if s["schedule"] == "Next Week"]

            return {
                "all_topics": schedule,
                "today": today,
                "tomorrow": tomorrow,
                "this_week": this_week,
                "next_week": next_week,
                "total_topics": len(schedule),
                "urgent_count": len(today) + len(tomorrow),
            }

        except Exception as e:
            print(f"[PRS] Error generating schedule: {e}")
            return {"all_topics": [], "today": [], "tomorrow": [], "this_week": [], "next_week": [], "total_topics": 0, "urgent_count": 0}
        finally:
            conn.close()

    def complete_revision(self, student_id, topic, new_mastery):
        """Mark revision as completed and update mastery."""
        conn = get_db()
        try:
            conn.execute(
                """UPDATE revision_schedule SET status='completed', mastery_at_revision=?,
                   updated_at=datetime('now') WHERE student_id=? AND topic=?""",
                (new_mastery, student_id, topic)
            )
            conn.execute(
                "UPDATE topic_mastery SET mastery_pct=? WHERE student_id=? AND topic=?",
                (new_mastery, student_id, topic)
            )
            conn.commit()
        except Exception as e:
            print(f"[PRS] Error completing revision: {e}")
        finally:
            conn.close()

    def _get_schedule(self, rps):
        for threshold, days, label in self.SCHEDULE_THRESHOLDS:
            if rps >= threshold:
                return label, days
        return "Next Week", 7

    def _estimate_time(self, wrong_count, mastery_pct):
        base = 10
        if mastery_pct < 40:
            base += 15
        elif mastery_pct < 70:
            base += 8
        base += min(wrong_count, 10) * 2
        return base

    def _save_schedule(self, student_id, schedule):
        conn = get_db()
        try:
            for item in schedule:
                conn.execute(
                    """INSERT OR REPLACE INTO revision_schedule
                       (student_id, topic, priority_score, next_revision_date, status,
                        mastery_at_revision, estimated_minutes, updated_at)
                       VALUES (?, ?, ?, ?, 'pending', ?, ?, datetime('now'))""",
                    (student_id, item["topic"], item["rps"], item["next_revision_date"],
                     item["mastery_pct"], item["estimated_minutes"])
                )
            conn.commit()
        except Exception as e:
            print(f"[PRS] Error saving schedule: {e}")
        finally:
            conn.close()

    def _default_result(self, topic):
        return {
            "topic": topic, "rps": 0, "wrong_ratio": 0, "wrong_count": 0,
            "mastery_pct": 0, "avg_response_time": 0, "time_score": 0,
            "days_since_revision": 0, "schedule": "Next Week",
            "next_revision_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "estimated_minutes": 15,
            "breakdown": {"wrong_attempt_score": 0, "mastery_score": 0, "time_score": 0, "recency_score": 0}
        }
