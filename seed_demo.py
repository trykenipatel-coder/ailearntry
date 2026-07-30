"""
DEMO DATA SEEDER
Creates:
- 1 DSA Quiz by Dr. Smith (10 real DSA questions)
- 40 sample students
- Quiz attempts with realistic patterns (cheating, varying performance)
- Multi-use access code for demo
"""
import sqlite3
import hashlib
import random
import string
import secrets
from datetime import datetime, timedelta

DB_PATH = "learning_system.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def gen_code(conn):
    last = conn.execute("SELECT student_code FROM students WHERE student_code != '' ORDER BY student_code DESC LIMIT 1").fetchone()
    if last and last["student_code"]:
        num = int(last["student_code"].replace("APLS", "")) + 1
    else:
        num = 1
    return f"APLS{num:03d}"

def gen_access_code():
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))

def seed():
    db = get_db()
    c = db.cursor()

    # ═══ 1. GET MENTOR (Dr. Smith) ═══
    mentor = c.execute("SELECT * FROM mentors WHERE email = 'mentor@system.com'").fetchone()
    if not mentor:
        c.execute("INSERT INTO mentors (mentor_name, email, password, subject) VALUES (?, ?, ?, ?)",
                  ("Dr. Smith", "mentor@system.com", hashlib.sha256("mentor123".encode()).hexdigest(), "Computer Science"))
        db.commit()
        mentor = c.execute("SELECT * FROM mentors WHERE email = 'mentor@system.com'").fetchone()
    mentor_id = mentor["mentor_id"]
    print(f"[OK] Mentor: Dr. Smith (ID: {mentor_id})")

    # ═══ 2. CREATE DSA QUIZ WITH 10 REAL QUESTIONS ═══
    existing_quiz = c.execute("SELECT * FROM quizzes WHERE topic = 'DSA Comprehensive Assessment' AND created_by = ?", (mentor_id,)).fetchone()
    if existing_quiz:
        quiz_id = existing_quiz["quiz_id"]
        print(f"[OK] DSA Quiz already exists (ID: {quiz_id})")
    else:
        c.execute("INSERT INTO quizzes (topic, subject, difficulty, created_by, created_by_type, status) VALUES (?, ?, ?, ?, 'mentor', 'published')",
                  ("DSA Comprehensive Assessment", "Computer Science", "Mixed", mentor_id))
        quiz_id = c.lastrowid

        questions = [
            {
                "q": "What is the time complexity of binary search on a sorted array of n elements?",
                "a": "O(log n)", "b": "O(n)", "c": "O(n log n)", "d": "O(1)",
                "ans": "A", "diff": "Easy"
            },
            {
                "q": "Which data structure uses FIFO (First In First Out) principle?",
                "a": "Stack", "b": "Queue", "c": "Binary Tree", "d": "Hash Table",
                "ans": "B", "diff": "Easy"
            },
            {
                "q": "What is the worst-case time complexity of Quick Sort?",
                "a": "O(n log n)", "b": "O(n)", "c": "O(n^2)", "d": "O(log n)",
                "ans": "C", "diff": "Medium"
            },
            {
                "q": "In a max-heap, the parent node is always __________ than its children.",
                "a": "Smaller", "b": "Equal", "c": "Greater", "d": "Unrelated",
                "ans": "C", "diff": "Medium"
            },
            {
                "q": "Which traversal of a BST gives elements in sorted (ascending) order?",
                "a": "Pre-order", "b": "Post-order", "c": "In-order", "d": "Level-order",
                "ans": "C", "diff": "Easy"
            },
            {
                "q": "What is the space complexity of Merge Sort?",
                "a": "O(1)", "b": "O(log n)", "c": "O(n)", "d": "O(n^2)",
                "ans": "C", "diff": "Medium"
            },
            {
                "q": "Which of the following is NOT a self-balancing BST?",
                "a": "AVL Tree", "b": "Red-Black Tree", "c": "B-Tree", "d": "Binary Search Tree",
                "ans": "D", "diff": "Medium"
            },
            {
                "q": "Dijkstra's algorithm is used to find __________ in a weighted graph.",
                "a": "Minimum Spanning Tree", "b": "Shortest Path", "c": "Maximum Flow", "d": "Strongly Connected Components",
                "ans": "B", "diff": "Hard"
            },
            {
                "q": "What is the amortized time complexity of push and pop operations in a dynamic array (like Java's ArrayList)?",
                "a": "O(n)", "b": "O(log n)", "c": "O(1)", "d": "O(n^2)",
                "ans": "C", "diff": "Hard"
            },
            {
                "q": "In dynamic programming, what does the term 'overlapping subproblems' refer to?",
                "a": "Solving the same subproblem multiple times", "b": "Problems with no optimal substructure",
                "c": "Problems that cannot be divided", "d": "Problems with a single solution",
                "ans": "A", "diff": "Hard"
            }
        ]

        for q in questions:
            c.execute("""INSERT INTO questions
                (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (quiz_id, q["q"], q["a"], q["b"], q["c"], q["d"], q["ans"], q["diff"]))

        db.commit()
        print(f"[OK] DSA Quiz created (ID: {quiz_id}) with 10 questions")

    # ═══ 3. CREATE ACCESS CODE (multi-use for demo) ═══
    existing_code = c.execute("SELECT * FROM access_codes WHERE quiz_id = ? AND type = 'primary'", (quiz_id,)).fetchone()
    if existing_code:
        access_code = existing_code["code"]
        # Update to allow multiple uses
        c.execute("UPDATE access_codes SET max_attempts = 999 WHERE code_id = ?", (existing_code["code_id"],))
        print(f"[OK] Access Code: {access_code} (already exists, set to multi-use)")
    else:
        access_code = gen_access_code()
        c.execute("""INSERT INTO access_codes (quiz_id, code, type, status, max_attempts)
                     VALUES (?, ?, 'primary', 'active', 999)""",
                  (quiz_id, access_code))
        print(f"[OK] Access Code: {access_code} (created, multi-use)")

    db.commit()

    # ═══ 4. CREATE 40 SAMPLE STUDENTS ═══
    FIRST_NAMES = ["Aarav","Vivaan","Aditya","Vihaan","Arjun","Sai","Reyansh","Ayaan","Ishaan","Dhruv",
                   "Ananya","Riya","Shreya","Priya","Sneha","Aisha","Isha","Maya","Neha","Kavya",
                   "Rohan","Amit","Vikas","Sunil","Kiran","Rajesh","Deepak","Manoj","Sanjay","Vijay",
                   "Pooja","Anjali","Divya","Swati","Komal","Ritu","Nisha","Geeta","Meena","Rekha"]
    LAST_NAMES = ["Sharma","Verma","Patel","Gupta","Reddy","Singh","Kumar","Jain","Mehta","Shah",
                  "Desai","Joshi","Pandey","Mishra","Agarwal","Rao","Choudhary","Nair","Iyer","Menon",
                  "Bose","Sen","Das","Ghosh","Roy","Sarkar","Banerjee","Chakraborty","Mukherjee","Dasgupta",
                  "Naik","Pawar","Patil","Deshmukh","Kulkarni","Wagh","More","Sawant","Mahajan","Gokhale"]
    COURSES = ["Computer Science","Information Technology","Data Science","AI & ML","Electronics"]

    used = set()
    student_ids = []

    existing_students = c.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    if existing_students > 40:
        student_ids = [s["student_id"] for s in c.execute("SELECT student_id FROM students ORDER BY student_id DESC LIMIT 40").fetchall()]
        print(f"[OK] Using {len(student_ids)} existing students")
    else:
        for i in range(40):
            while True:
                fn = FIRST_NAMES[i % len(FIRST_NAMES)]
                ln = LAST_NAMES[i % len(LAST_NAMES)]
                name = f"{fn} {ln}"
                if name not in used:
                    used.add(name)
                    break
                fn = random.choice(FIRST_NAMES)
                ln = random.choice(LAST_NAMES)
                name = f"{fn} {ln}"
                if name not in used:
                    used.add(name)
                    break

            email = f"{fn.lower()}.{ln.lower()}{i+1}@gmail.com"
            pwd = hashlib.sha256("student123".encode()).hexdigest()
            course = random.choice(COURSES)
            code = gen_code(db)
            reg = (datetime.now() - timedelta(days=random.randint(15, 90))).strftime("%Y-%m-%d %H:%M:%S")

            c.execute("INSERT INTO students (name, email, password, course, registration_date, student_code) VALUES (?, ?, ?, ?, ?, ?)",
                      (name, email, pwd, course, reg, code))
            sid = c.lastrowid
            student_ids.append(sid)

        db.commit()
        print(f"[OK] Created {len(student_ids)} students")

    # ═══ 5. QUIZ ATTEMPTS — REALISTIC PATTERNS ═══
    # Clear existing results for this quiz
    c.execute("DELETE FROM quiz_results WHERE quiz_id = ?", (quiz_id,))
    c.execute("DELETE FROM violations WHERE quiz_id = ?", (quiz_id,))

    total_questions = 10
    correct_answers = ["A","B","C","C","B","C","D","B","C","A"]

    patterns = {
        "topper": {"range": (8, 10), "time": (90, 180), "count": 6},
        "good": {"range": (6, 8), "time": (100, 240), "count": 10},
        "average": {"range": (4, 6), "time": (120, 300), "count": 12},
        "weak": {"range": (1, 4), "time": (60, 200), "count": 7},
        "cheater_fast": {"range": (9, 10), "time": (15, 35), "count": 3, "cheat": True},
        "cheater_tab": {"range": (7, 9), "time": (60, 120), "count": 2, "cheat": True, "tab": True},
        "sleeper": {"range": (2, 5), "time": (300, 500), "count": 2},
    }

    student_idx = 0
    for pattern_name, cfg in patterns.items():
        for _ in range(cfg["count"]):
            if student_idx >= len(student_ids):
                break
            sid = student_ids[student_idx]
            student_idx += 1

            marks = random.randint(cfg["range"][0], cfg["range"][1])
            accuracy = round((marks / total_questions) * 100, 1)
            status = "Pass" if accuracy >= 40 else "Fail"
            time_taken = random.randint(cfg["time"][0], cfg["time"][1])

            days_ago = random.randint(1, 30)
            dt = (datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 12))).strftime("%Y-%m-%d %H:%M:%S")

            c.execute("""INSERT INTO quiz_results
                (student_id, quiz_id, marks, total_questions, accuracy, topic, difficulty, time_taken, status, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, quiz_id, marks, total_questions, accuracy, "DSA Comprehensive Assessment", "Mixed", time_taken, status, dt))

            # Add cheating violations
            if cfg.get("cheat"):
                num_violations = random.randint(2, 5)
                sources = []
                if cfg.get("tab"):
                    sources.extend(["tab_switch", "tab_switch", "window_blur"])
                else:
                    sources.extend(["tab_switch", "devtools", "print_screen", "tab_switch", "copy_paste"])
                src = ",".join(random.sample(sources, min(num_violations, len(sources))))
                vdt = dt
                c.execute("""INSERT INTO violations (student_id, quiz_id, warning_count, date, source)
                             VALUES (?, ?, ?, ?, ?)""",
                          (sid, quiz_id, num_violations, vdt, src))

            # Streak
            current = random.randint(0, 20) if pattern_name in ("topper", "good") else random.randint(0, 5)
            longest = max(current, random.randint(1, 25))
            last_quiz = (datetime.now() - timedelta(days=random.randint(0, 3))).strftime("%Y-%m-%d")
            c.execute("DELETE FROM student_streaks WHERE student_id = ?", (sid,))
            c.execute("INSERT INTO student_streaks (student_id, current_streak, longest_streak, last_quiz_date) VALUES (?, ?, ?, ?)",
                      (sid, current, longest, last_quiz))

    db.commit()

    # ═══ 6. ADD BADGES FOR TOP PERFORMERS ═══
    c.execute("DELETE FROM badges WHERE mentor_id = ?", (mentor_id,))
    badge_data = [
        ("Star Performer", "\u2b50", "Outstanding DSA performance"),
        ("Quick Learner", "\U0001f680", "Fastest improvement in DSA"),
        ("Consistent Scholar", "\U0001f4da", "Consistent high scores"),
        ("Top Scorer", "\U0001f3c6", "Highest accuracy in DSA quiz"),
        ("Code Master", "\U0001f3af", "Excellent problem solving"),
    ]
    for sid in student_ids[:8]:
        b = random.choice(badge_data)
        c.execute("INSERT INTO badges (student_id, mentor_id, badge_name, badge_icon, description) VALUES (?, ?, ?, ?, ?)",
                  (sid, mentor_id, b[0], b[1], b[2]))

    # ═══ 7. ADD FEEDBACK ═══
    c.execute("DELETE FROM feedback WHERE mentor_id = ?", (mentor_id,))
    comments = [
        "Excellent problem-solving skills!", "Needs more practice with DP problems.",
        "Strong in graphs, weak in trees.", "Very consistent performer.",
        "Should focus on time complexity analysis.", "Great improvement over last month!",
        "One of the best students in the cohort.", "Works hard, results show it.",
        "Struggles with recursion concepts.", "Top 5% of the class."
    ]
    for sid in student_ids[:20]:
        rating = random.randint(3, 5)
        comment = random.choice(comments)
        dt = (datetime.now() - timedelta(days=random.randint(1, 20))).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO feedback (student_id, mentor_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
                  (sid, mentor_id, rating, comment, dt))

    db.commit()
    db.close()

    print()
    print("=" * 60)
    print("  DEMO DATA SEED COMPLETE!")
    print("=" * 60)
    print(f"  Quiz: DSA Comprehensive Assessment (ID: {quiz_id})")
    print(f"  Access Code: {access_code}")
    print(f"  Questions: 10 DSA questions")
    print(f"  Students: {len(student_ids)}")
    print(f"  Attempts: ~{sum(p['count'] for p in patterns.values())} quiz attempts")
    print(f"  Cheaters: {patterns['cheater_fast']['count'] + patterns['cheater_tab']['count']} students")
    print()
    print("  Login: mentor@system.com / mentor123")
    print("  Access Code: " + access_code)
    print("=" * 60)


if __name__ == "__main__":
    seed()
