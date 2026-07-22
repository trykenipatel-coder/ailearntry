from database import get_db
from datetime import datetime

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def _mean(values):
    if not values:
        return 0
    return sum(values) / len(values)


def analyze_learning_heartbeat(student_id):
    db = get_db()
    results = db.execute(
        """SELECT accuracy, time_taken, date, difficulty FROM quiz_results
           WHERE student_id = ? ORDER BY date ASC""",
        (student_id,),
    ).fetchall()
    db.close()

    if not results or len(results) < 3:
        return {
            "best_time": None,
            "optimal_duration": None,
            "attention_decay": None,
            "message": "Need at least 3 quiz results for heartbeat analysis.",
        }

    time_buckets = {"morning": [], "afternoon": [], "evening": []}
    durations = []
    performances = []

    for r in results:
        try:
            dt = datetime.strptime(r["date"][:19] if r["date"] else "", "%Y-%m-%d %H:%M:%S")
        except (ValueError, IndexError):
            continue
        hour = dt.hour
        if 5 <= hour < 12:
            bucket = "morning"
        elif 12 <= hour < 17:
            bucket = "afternoon"
        else:
            bucket = "evening"
        time_buckets[bucket].append(r["accuracy"])
        durations.append(r["time_taken"])
        performances.append(r["accuracy"])

    best_time = max(time_buckets, key=lambda b: _mean(time_buckets[b]) if time_buckets[b] else 0)
    best_avg = round(_mean(time_buckets[best_time]), 2) if time_buckets[best_time] else 0

    if len(durations) >= 3 and SKLEARN_AVAILABLE and NUMPY_AVAILABLE:
        X = np.array(durations).reshape(-1, 1)
        y = np.array(performances)
        kmeans = KMeans(n_clusters=min(3, len(set(durations))), random_state=42, n_init=5)
        clusters = kmeans.fit_predict(X)
        cluster_perf = {}
        for i, c in enumerate(clusters):
            cluster_perf.setdefault(c, []).append(performances[i])
        best_cluster = max(cluster_perf, key=lambda c: _mean(cluster_perf[c]))
        optimal_duration = round(_mean([durations[i] for i, c in enumerate(clusters) if c == best_cluster]))
    else:
        optimal_duration = round(_mean(durations)) if durations else 0

    decay = None
    if len(performances) >= 5:
        half = len(performances) // 2
        first_half = _mean(performances[:half])
        second_half = _mean(performances[half:])
        decay = round(first_half - second_half, 2)

    return {
        "best_time": {"label": best_time.capitalize(), "avg_accuracy": best_avg},
        "optimal_duration": optimal_duration,
        "attention_decay": decay if decay and decay > 0 else None,
        "total_sessions": len(results),
        "message": "Learning heartbeat analyzed from historical quiz data.",
    }
