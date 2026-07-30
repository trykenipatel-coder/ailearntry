import json
from database import get_db

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from sklearn.linear_model import LogisticRegression, LinearRegression
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def _mean(values):
    if not values:
        return 0
    return sum(values) / len(values)


def train_pass_fail_model(student_id=None):
    if not SKLEARN_AVAILABLE or not NUMPY_AVAILABLE:
        return None

    db = get_db()
    if student_id:
        results = db.execute(
            """SELECT marks, total_questions, accuracy, time_taken,
                      CASE WHEN status='Pass' THEN 1 ELSE 0 END as passed
               FROM quiz_results WHERE student_id = ?""",
            (student_id,),
        ).fetchall()
    else:
        results = db.execute(
            """SELECT marks, total_questions, accuracy, time_taken,
                      CASE WHEN status='Pass' THEN 1 ELSE 0 END as passed
               FROM quiz_results"""
        ).fetchall()
    db.close()

    if len(results) < 3:
        return None

    X = np.array([[r["marks"], r["total_questions"], r["accuracy"], r["time_taken"]] for r in results])
    y = np.array([r["passed"] for r in results])

    try:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model = LogisticRegression(random_state=42)
        model.fit(X_scaled, y)
        return {"model": model, "scaler": scaler}
    except Exception:
        return None


def predict_performance(student_id):
    db = get_db()
    results = db.execute(
        """SELECT marks, total_questions, accuracy, time_taken, status
           FROM quiz_results WHERE student_id = ? ORDER BY date DESC""",
        (student_id,),
    ).fetchall()
    db.close()

    if not results:
        return {
            "predicted_score": None,
            "pass_probability": None,
            "trend": "insufficient_data",
            "message": "Need more quiz data to make predictions.",
        }

    recent = list(results[:3])
    avg_accuracy = _mean([r["accuracy"] for r in recent]) if recent else 0
    total_attempts = len(results)
    pass_count = sum(1 for r in results if r["status"] == "Pass")
    pass_rate = pass_count / total_attempts if total_attempts > 0 else 0

    if total_attempts >= 2:
        accuracies = [r["accuracy"] for r in results]
        trend = "improving" if accuracies[0] > accuracies[-1] else "declining" if accuracies[0] < accuracies[-1] else "stable"
    else:
        trend = "stable"

    if len(results) >= 3:
        weights = [0.5, 0.3, 0.2]
        predicted_score = sum(r["accuracy"] * w for r, w in zip(recent, weights[:len(recent)]))
    elif len(results) >= 1:
        predicted_score = avg_accuracy
    else:
        predicted_score = 50

    pass_prob = pass_rate * 100

    avg_time = _mean([r["time_taken"] for r in results]) if results else 0
    if avg_time < 5:
        learning_speed = "Fast"
    elif avg_time < 10:
        learning_speed = "Medium"
    else:
        learning_speed = "Slow"

    return {
        "predicted_score": round(predicted_score, 2),
        "pass_probability": round(pass_prob, 2),
        "trend": trend,
        "learning_speed": learning_speed,
        "total_attempts": total_attempts,
        "avg_accuracy": round(avg_accuracy, 2),
        "pass_rate": round(pass_rate * 100, 2),
        "message": "Prediction based on historical performance data.",
    }


def get_knowledge_gaps(student_id):
    db = get_db()
    results = db.execute(
        """SELECT qr.topic, COUNT(*) as attempts,
                  ROUND(AVG(qr.accuracy), 2) as avg_accuracy,
                  SUM(CASE WHEN qr.status='Fail' THEN 1 ELSE 0 END) as fails
           FROM quiz_results qr
           WHERE qr.student_id = ?
           GROUP BY qr.topic""",
        (student_id,),
    ).fetchall()
    db.close()

    gaps = []
    for r in results:
        if r["avg_accuracy"] < 60 or r["fails"] > r["attempts"] / 2:
            gaps.append({
                "topic": r["topic"],
                "accuracy": r["avg_accuracy"],
                "attempts": r["attempts"],
                "fails": r["fails"],
                "weakness_level": "weak" if r["avg_accuracy"] < 40 else "needs_improvement",
            })

    return gaps
