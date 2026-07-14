import math
from database import get_db
from datetime import datetime, timedelta


def calculate_retention(student_id):
    db = get_db()
    results = db.execute(
        """SELECT accuracy, time_taken, date FROM quiz_results
           WHERE student_id = ? ORDER BY date DESC""",
        (student_id,),
    ).fetchall()
    db.close()

    if not results or len(results) < 2:
        return {
            "success": True,
            "retention_pct": None,
            "days_until_forget": None,
            "needs_review": False,
            "message": "Need at least 2 quiz results to calculate retention.",
        }

    scores = [r["accuracy"] for r in results]
    times = [r["time_taken"] for r in results]
    recent = results[0]

    avg_time = sum(times) / len(times)
    learning_speed = max(0.05, min(1.0, avg_time / 120))

    try:
        last_date = datetime.strptime(recent["date"][:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        last_date = datetime.now()
    days_since = (datetime.now() - last_date).days

    retention = math.exp(-learning_speed * days_since)
    retention_pct = round(retention * 100, 1)

    threshold = 0.5
    if retention > threshold:
        days_until_forget = round(-math.log(threshold) / learning_speed - days_since, 1)
        if days_until_forget < 0:
            days_until_forget = 0
    else:
        days_until_forget = 0

    needs_review = retention < 0.5
    recent_avg = sum(scores[:3]) / min(len(scores), 3)

    return {
        "success": True,
        "retention_pct": retention_pct,
        "days_since_last_study": days_since,
        "days_until_forget": round(days_until_forget, 1),
        "needs_review": needs_review,
        "learning_speed_factor": round(learning_speed, 2),
        "recent_avg_score": round(recent_avg, 1),
        "message": f"Retention: {retention_pct}% — {'Review needed!' if needs_review else 'Good retention level.'}",
    }
