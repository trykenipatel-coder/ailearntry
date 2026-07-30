"""Coding Resource Explorer — search, recommend, favorite, track resources."""
import sys, os, sqlite3, json
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db

PLATFORMS = {
    "GeeksforGeeks": {"base": "https://www.geeksforgeeks.org", "color": "#2f8d46"},
    "LeetCode": {"base": "https://leetcode.com", "color": "#ffa116"},
    "HackerRank": {"base": "https://www.hackerrank.com", "color": "#1ba94c"},
    "HackerEarth": {"base": "https://www.hackerearth.com", "color": "#3c78d8"},
    "Codeforces": {"base": "https://codeforces.com", "color": "#1b68b3"},
    "CodeChef": {"base": "https://www.codechef.com", "color": "#8b4513"},
    "AtCoder": {"base": "https://atcoder.jp", "color": "#333"},
}

CATEGORIES = [
    {"name": "Data Structures", "icon": "📘", "topics": ["Arrays", "Strings", "Linked List", "Stack", "Queue", "Trees", "Graph", "Hash Table", "Heap", "Trie"]},
    {"name": "Algorithms", "icon": "⚡", "topics": ["Sorting", "Searching", "Dynamic Programming", "Greedy", "Backtracking", "Divide and Conquer", "Graph Algorithms", "Recursion"]},
    {"name": "Web Development", "icon": "💻", "topics": ["HTML", "CSS", "JavaScript", "React", "Node.js", "Django", "Flask", "API"]},
    {"name": "Artificial Intelligence", "icon": "🤖", "topics": ["Machine Learning", "Deep Learning", "NLP", "Computer Vision", "Neural Networks"]},
    {"name": "Database", "icon": "🗃", "topics": ["SQL", "NoSQL", "MongoDB", "MySQL", "PostgreSQL", "Database Design"]},
    {"name": "Programming Languages", "icon": "🐍", "topics": ["Python", "Java", "C++", "JavaScript", "Go", "C", "Rust"]},
]

POPULAR_TOPICS = ["Arrays", "Strings", "Linked List", "Stack", "Queue", "Trees", "Graph", "Dynamic Programming", "SQL", "OOP", "Sorting", "Recursion", "Binary Search", "Greedy", "Backtracking"]

FEATURED = [
    {"title": "Top 100 DSA Questions", "topic": "DSA", "platform": "GeeksforGeeks", "difficulty": "Mixed", "time": "120 min", "url": "https://www.geeksforgeeks.org/must-do-coding-questions-for-product-based-companies/"},
    {"title": "SQL Interview Preparation", "topic": "SQL", "platform": "GeeksforGeeks", "difficulty": "Medium", "time": "60 min", "url": "https://www.geeksforgeeks.org/sql-interview-question/"},
    {"title": "Google Coding Interview Guide", "topic": "Interview", "platform": "LeetCode", "difficulty": "Hard", "time": "90 min", "url": "https://leetcode.com/explore/"},
    {"title": "System Design Basics", "topic": "System Design", "platform": "GeeksforGeeks", "difficulty": "Medium", "time": "45 min", "url": "https://www.geeksforgeeks.org/system-design-tutorial/"},
    {"title": "Python Programming Roadmap", "topic": "Python", "platform": "GeeksforGeeks", "difficulty": "Easy", "time": "30 min", "url": "https://www.geeksforgeeks.org/python-programming-language-tutorial/"},
    {"title": "Dynamic Programming Patterns", "topic": "Dynamic Programming", "platform": "LeetCode", "difficulty": "Hard", "time": "60 min", "url": "https://leetcode.com/discuss/general-discussion/458695/dynamic-programming-patterns"},
]


def get_resource_url(topic, platform):
    t = topic.lower().replace(" ", "-").replace("+", "p")
    p = platform.lower().replace(" ", "")
    urls = {
        "GeeksforGeeks": f"https://www.geeksforgeeks.org/{t}/",
        "LeetCode": f"https://leetcode.com/tag/{t}/",
        "HackerRank": f"https://www.hackerrank.com/domains/{t}",
        "HackerEarth": f"https://www.hackerearth.com/practice/{t}/",
        "Codeforces": f"https://codeforces.com/problemset/tag/{t}",
        "CodeChef": f"https://www.codechef.com/problems/tag/{t}",
        "AtCoder": f"https://atcoder.jp/contests/practice2/tasks",
    }
    return urls.get(platform, f"https://www.google.com/search?q={topic}+{platform}+practice")


class ResourceExplorer:
    def search(self, topic):
        results = []
        diff_times = {
            "GeeksforGeeks": ("Easy", "25 min"),
            "LeetCode": ("Medium", "35 min"),
            "HackerRank": ("Easy", "20 min"),
            "HackerEarth": ("Medium", "30 min"),
            "Codeforces": ("Hard", "45 min"),
            "CodeChef": ("Medium", "30 min"),
            "AtCoder": ("Medium", "35 min"),
        }
        for name, info in PLATFORMS.items():
            diff, time = diff_times.get(name, ("Medium", "30 min"))
            results.append({
                "platform": name,
                "title": f"{topic} Practice",
                "difficulty": diff,
                "estimated_time": time,
                "url": get_resource_url(topic, name),
                "color": info["color"],
            })
        return results

    def get_recommendations(self, student_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            mastery = conn.execute(
                "SELECT topic, mastery_pct FROM topic_mastery WHERE student_id=? AND mastery_pct < 50 ORDER BY mastery_pct ASC LIMIT 5",
                (student_id,)
            ).fetchall()

            recs = []
            platforms = ["GeeksforGeeks", "LeetCode", "HackerRank"]
            for i, m in enumerate(mastery):
                p = platforms[i % len(platforms)]
                recs.append({
                    "topic": m["topic"],
                    "platform": p,
                    "difficulty": "Easy" if m["mastery_pct"] < 30 else "Medium",
                    "estimated_time": "30 min",
                    "url": get_resource_url(m["topic"], p),
                    "mastery": round(m["mastery_pct"], 1),
                })
            return recs
        finally:
            conn.close()

    def log_open(self, student_id, topic, platform, category=""):
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO resource_history (student_id, topic, platform, category, opened_at) VALUES (?, ?, ?, ?, datetime('now'))",
                (student_id, topic, platform, category)
            )
            conn.commit()
        finally:
            conn.close()

    def get_recent(self, student_id, limit=5):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT DISTINCT topic, platform, opened_at FROM resource_history WHERE student_id=? ORDER BY opened_at DESC LIMIT ?",
                (student_id, limit)
            ).fetchall()
            result = []
            for r in rows:
                opened = r["opened_at"]
                try:
                    dt = datetime.strptime(opened, "%Y-%m-%d %H:%M:%S")
                    diff = datetime.now() - dt
                    if diff.days == 0:
                        time_str = "Today"
                    elif diff.days == 1:
                        time_str = "Yesterday"
                    elif diff.days < 7:
                        time_str = f"{diff.days} Days Ago"
                    else:
                        time_str = f"{diff.days // 7} Weeks Ago"
                except:
                    time_str = opened
                result.append({"topic": r["topic"], "platform": r["platform"], "time_ago": time_str})
            return result
        finally:
            conn.close()

    def toggle_favorite(self, student_id, topic, platform, category=""):
        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT fav_id FROM favorite_resources WHERE student_id=? AND topic=? AND platform=?",
                (student_id, topic, platform)
            ).fetchone()
            if existing:
                conn.execute("DELETE FROM favorite_resources WHERE fav_id=?", (existing[0],))
                conn.commit()
                return {"favorited": False}
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO favorite_resources (student_id, topic, platform, category) VALUES (?, ?, ?, ?)",
                    (student_id, topic, platform, category)
                )
                conn.commit()
                return {"favorited": True}
        finally:
            conn.close()

    def get_favorites(self, student_id):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM favorite_resources WHERE student_id=? ORDER BY added_at DESC",
                (student_id,)
            ).fetchall()
            return [{"topic": r["topic"], "platform": r["platform"], "category": r["category"], "added_at": r["added_at"]} for r in rows]
        finally:
            conn.close()

    def is_favorited(self, student_id, topic, platform):
        conn = get_db()
        try:
            r = conn.execute(
                "SELECT fav_id FROM favorite_resources WHERE student_id=? AND topic=? AND platform=?",
                (student_id, topic, platform)
            ).fetchone()
            return r is not None
        finally:
            conn.close()

    def get_analytics(self):
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            top_topic = conn.execute(
                "SELECT topic, COUNT(*) as cnt FROM resource_history GROUP BY topic ORDER BY cnt DESC LIMIT 1"
            ).fetchone()
            top_platform = conn.execute(
                "SELECT platform, COUNT(*) as cnt FROM resource_history GROUP BY platform ORDER BY cnt DESC LIMIT 1"
            ).fetchone()
            total_searches = conn.execute("SELECT COUNT(*) as cnt FROM resource_history").fetchone()["cnt"]
            unique_students = conn.execute("SELECT COUNT(DISTINCT student_id) as cnt FROM resource_history").fetchone()["cnt"]

            return {
                "most_searched_topic": top_topic["topic"] if top_topic else "—",
                "most_used_platform": top_platform["platform"] if top_platform else "—",
                "total_searches": total_searches,
                "unique_students": unique_students,
            }
        finally:
            conn.close()
