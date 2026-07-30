from database import get_db

try:
    from sklearn.ensemble import RandomForestClassifier
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def score_question_quality(quiz_id=None):
    db = get_db()
    if quiz_id:
        questions = db.execute(
            """SELECT q.question_id, q.question_text, q.difficulty,
                      COUNT(qr.result_id) as attempt_count,
                      COALESCE(ROUND(AVG(qr.time_taken), 1), 0) as avg_time,
                      COALESCE(ROUND(AVG(qr.accuracy), 2), 0) as success_rate
               FROM questions q
               LEFT JOIN quiz_results qr ON q.quiz_id = qr.quiz_id
               WHERE q.quiz_id = ?
               GROUP BY q.question_id""",
            (quiz_id,),
        ).fetchall()
    else:
        questions = db.execute(
            """SELECT q.question_id, q.question_text, q.difficulty,
                      COUNT(qr.result_id) as attempt_count,
                      COALESCE(ROUND(AVG(qr.time_taken), 1), 0) as avg_time,
                      COALESCE(ROUND(AVG(qr.accuracy), 2), 0) as success_rate
               FROM questions q
               LEFT JOIN quiz_results qr ON q.quiz_id = qr.quiz_id
               GROUP BY q.question_id
               ORDER BY attempt_count DESC LIMIT 50""",
        ).fetchall()
    db.close()

    if not questions:
        return {"success": False, "message": "No question data available."}

    results = []
    for q in questions:
        ac = q["attempt_count"] or 0
        at = q["avg_time"] or 0
        sr = q["success_rate"] or 0

        if ac < 5:
            quality = "INSUFFICIENT_DATA"
            label = "Not enough attempts"
        elif sr >= 90 and at <= 15:
            quality = "TOO_EASY"
            label = "Too Easy"
        elif sr <= 30 and at >= 60:
            quality = "TOO_HARD"
            label = "Too Hard"
        elif sr >= 40 and sr <= 85:
            quality = "GOOD"
            label = "Good"
        else:
            quality = "BADLY_WRITTEN"
            label = "Badly Written"

        results.append({
            "question_id": q["question_id"],
            "question_text": q["question_text"][:80],
            "difficulty": q["difficulty"],
            "attempt_count": ac,
            "avg_time_seconds": at,
            "success_rate": sr,
            "quality": quality,
            "label": label,
        })

    return {"success": True, "questions": results}
