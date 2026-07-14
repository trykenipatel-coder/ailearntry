from database import get_db

try:
    from sklearn.ensemble import RandomForestRegressor
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def estimate_confidence_gap(student_id):
    db = get_db()
    results = db.execute(
        """SELECT accuracy, time_taken, marks, total_questions, date
           FROM quiz_results WHERE student_id = ? ORDER BY date ASC""",
        (student_id,),
    ).fetchall()
    db.close()

    if not results or len(results) < 2:
        return {
            "success": True,
            "gap_type": "INSUFFICIENT_DATA",
            "label": "Need more data",
            "confidence_score": None,
            "actual_avg": None,
        }

    scores = [r["accuracy"] for r in results]
    times = [r["time_taken"] for r in results]
    actual_avg = sum(scores) / len(scores)

    estimated_self_score = 0
    for r in results:
        marks = r["marks"] or 0
        total = r["total_questions"] or 1
        estimated_self_score += (marks / total) * 100
    estimated_self_score = estimated_self_score / len(results) if results else 50

    adjusted = estimated_self_score * (0.9 if actual_avg < 50 else 1.0)
    gap = adjusted - actual_avg

    avg_time = sum(times) / len(times)
    if avg_time < 20 and gap > 15:
        gap_type = "OVERCONFIDENT"
        label = "Overconfident"
    elif gap < -15:
        gap_type = "UNDERCONFIDENT"
        label = "Underconfident"
    else:
        gap_type = "ACCURATE"
        label = "Accurate Self-Assessment"

    return {
        "success": True,
        "gap_type": gap_type,
        "label": label,
        "confidence_score": round(adjusted, 1),
        "actual_avg": round(actual_avg, 1),
        "gap": round(gap, 1),
        "total_quizzes": len(results),
    }
