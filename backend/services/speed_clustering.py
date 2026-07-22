from database import get_db

try:
    from sklearn.cluster import KMeans
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


def cluster_learning_speed():
    db = get_db()
    students = db.execute(
        """SELECT s.student_id, s.name,
                  COALESCE(ROUND(AVG(qr.accuracy), 2), 0) as avg_score,
                  COALESCE(ROUND(AVG(qr.time_taken), 1), 0) as avg_time,
                  COALESCE(ROUND(COUNT(qr.result_id) * 1.0 / MAX(1, COUNT(DISTINCT qr.quiz_id))), 1) as attempts_per_quiz
           FROM students s
           LEFT JOIN quiz_results qr ON s.student_id = qr.student_id
           GROUP BY s.student_id
           HAVING COUNT(qr.result_id) > 0""",
    ).fetchall()
    db.close()

    if not students or len(students) < 3:
        return {"success": False, "message": "Need at least 3 students with data."}

    data = []
    for s in students:
        data.append([s["avg_score"], s["avg_time"], s["attempts_per_quiz"]])

    if SKLEARN_AVAILABLE:
        X = np.array(data)
        n_clusters = min(3, len(students))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=5)
        clusters = kmeans.fit_predict(X)

        cluster_centers = {}
        for i, c in enumerate(clusters):
            cluster_centers.setdefault(c, []).append(data[i][0])
        cluster_types = {}
        for c, scores in cluster_centers.items():
            avg_s = sum(scores) / len(scores)
            if avg_s >= 70:
                cluster_types[c] = "FAST"
            elif avg_s >= 45:
                cluster_types[c] = "MEDIUM"
            else:
                cluster_types[c] = "SLOW"
    else:
        clusters = []
        for d in data:
            if d[0] >= 70:
                clusters.append(0)
            elif d[0] >= 45:
                clusters.append(1)
            else:
                clusters.append(2)
        cluster_types = {0: "FAST", 1: "MEDIUM", 2: "SLOW"}

    students_list = []
    type_counts = {"FAST": 0, "MEDIUM": 0, "SLOW": 0}
    for i, s in enumerate(students):
        c = clusters[i]
        stype = cluster_types.get(c, "MEDIUM")
        type_counts[stype] = type_counts.get(stype, 0) + 1
        students_list.append({
            "student_id": s["student_id"],
            "name": s["name"],
            "avg_score": s["avg_score"],
            "avg_time": s["avg_time"],
            "type": stype,
        })

    return {"success": True, "students": students_list, "type_distribution": type_counts}
