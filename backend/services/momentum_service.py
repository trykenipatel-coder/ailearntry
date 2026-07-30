from database import get_db

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


def _mean(values):
    if not values:
        return 0
    return sum(values) / len(values)


def _std(values):
    if not values or len(values) < 2:
        return 0
    m = _mean(values)
    return (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def analyze_study_momentum(student_id):
    db = get_db()
    results = db.execute(
        """SELECT accuracy, date, status FROM quiz_results
           WHERE student_id = ? ORDER BY date ASC""",
        (student_id,),
    ).fetchall()

    streak = db.execute(
        "SELECT current_streak, longest_streak, last_quiz_date FROM student_streaks WHERE student_id = ?",
        (student_id,),
    ).fetchone()
    db.close()

    if not results or len(results) < 2:
        return {
            "momentum_index": None,
            "momentum_label": "Insufficient Data",
            "quit_risk": None,
            "current_streak": streak["current_streak"] if streak else 0,
            "longest_streak": streak["longest_streak"] if streak else 0,
            "message": "Need more quiz data to calculate momentum.",
        }

    accuracies = [r["accuracy"] for r in results]
    n = len(accuracies)

    recent = accuracies[-3:] if n >= 3 else accuracies
    older = accuracies[:-3] if n >= 6 else accuracies[:len(accuracies)//2]

    recent_avg = _mean(recent)
    older_avg = _mean(older) if len(older) >= 2 else recent_avg

    trend_slope = (accuracies[-1] - accuracies[0]) / max(n - 1, 1)

    consistency = 1.0 - min(_std(accuracies) / 50.0, 1.0)

    streak_bonus = min((streak["current_streak"] if streak else 0) * 2, 20)

    momentum_index = round(min(max((recent_avg - older_avg) * 0.3 + trend_slope * 0.4 + consistency * 30 + streak_bonus, 0), 100))

    if momentum_index >= 65:
        momentum_label = "Strong Momentum"
    elif momentum_index >= 40:
        momentum_label = "Building Momentum"
    elif momentum_index >= 20:
        momentum_label = "Stable"
    else:
        momentum_label = "Declining"

    quit_risk_score = 0
    if n >= 2:
        recent_3 = accuracies[-3:] if n >= 3 else accuracies
        if all(a < 35 for a in recent_3):
            quit_risk_score += 40
        elif all(a < 50 for a in recent_3):
            quit_risk_score += 20

    if streak and streak["current_streak"] == 0:
        quit_risk_score += 15
    elif streak and streak["current_streak"] >= 7:
        quit_risk_score -= 20

    if len(results) <= 2:
        quit_risk_score += 10

    if trend_slope < -5:
        quit_risk_score += 15
    elif trend_slope > 5:
        quit_risk_score -= 15

    if n >= 3 and all(r["status"] == "Fail" for r in results[-3:]):
        quit_risk_score += 25

    quit_risk_score = max(0, min(100, quit_risk_score))

    if quit_risk_score >= 60:
        quit_risk_label = "High Risk"
    elif quit_risk_score >= 30:
        quit_risk_label = "Medium Risk"
    else:
        quit_risk_label = "Low Risk"

    return {
        "momentum_index": momentum_index,
        "momentum_label": momentum_label,
        "trend_slope": round(trend_slope, 2),
        "recent_avg": round(recent_avg, 2),
        "overall_avg": round(_mean(accuracies), 2),
        "consistency": round(consistency * 100, 1),
        "current_streak": streak["current_streak"] if streak else 0,
        "longest_streak": streak["longest_streak"] if streak else 0,
        "quit_risk": {"score": quit_risk_score, "label": quit_risk_label},
        "total_quizzes": n,
        "message": "Momentum analysis based on performance trajectory.",
    }
