import numpy as np
from database import get_db

try:
    from sklearn.ensemble import RandomForestClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def classify_mistakes(student_id):
    db = get_db()
    results = db.execute(
        """SELECT accuracy, time_taken, difficulty, marks, total_questions, status, date
           FROM quiz_results WHERE student_id = ? ORDER BY date ASC""",
        (student_id,),
    ).fetchall()
    db.close()

    if not results or len(results) < 3:
        return {
            "patterns": [],
            "dominant_pattern": None,
            "message": "Need at least 3 results to analyze mistake patterns.",
        }

    patterns = []
    for i, r in enumerate(results):
        accuracy = r["accuracy"]
        time_taken = r["time_taken"]
        difficulty = r["difficulty"] or "Medium"
        status = r["status"]

        perf_ratio = accuracy / 100.0
        time_per_q = time_taken / max(r["total_questions"], 1)

        if status == "Pass":
            patterns.append({
                "type": "no_error",
                "label": "No significant errors",
                "confidence": round(perf_ratio * 100, 1),
                "details": {"accuracy": accuracy, "time_per_question": round(time_per_q, 1)},
            })
            continue

        score = 0
        reasons = []

        if time_per_q < 3:
            score += 2
            reasons.append("rushed")
        elif time_per_q > 12:
            score += 2
            reasons.append("overthought")
        else:
            score += 1

        if accuracy < 30:
            score += 2
            reasons.append("knowledge_gap")
        elif accuracy < 50:
            score += 1
            reasons.append("borderline")

        if difficulty == "Hard" and accuracy < 40:
            score += 2
            reasons.append("difficulty_mismatch")

        if score >= 4:
            label = "Knowledge Gap"
            mtype = "knowledge_gap"
        elif score >= 2:
            label = "Difficulty Mismatch"
            mtype = "difficulty_mismatch"
        else:
            label = "Careless Error"
            mtype = "careless"

        patterns.append({
            "type": mtype,
            "label": label,
            "confidence": round(min(score / 6 * 100, 95), 1),
            "details": {"accuracy": accuracy, "time_per_question": round(time_per_q, 1), "difficulty": difficulty},
        })

    type_counts = {}
    for p in patterns:
        if p["type"] != "no_error":
            type_counts[p["type"]] = type_counts.get(p["type"], 0) + 1

    dominant = max(type_counts, key=type_counts.get) if type_counts else None
    dominant_label = {"careless": "Careless Errors", "knowledge_gap": "Knowledge Gaps", "difficulty_mismatch": "Difficulty Mismatch"}.get(dominant, None)

    return {
        "patterns": patterns,
        "dominant_pattern": {"type": dominant, "label": dominant_label} if dominant else None,
        "type_counts": type_counts,
        "total_errors": sum(type_counts.values()),
        "message": "Mistake patterns classified from quiz performance data.",
    }
