import sqlite3
import hashlib
import random
from config import DATABASE_PATH
from datetime import datetime, timedelta


def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            course TEXT DEFAULT '',
            registration_date TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS mentors (
            mentor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            mentor_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            subject TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            approved_by INTEGER NULL,
            approved_at TEXT NULL
        );

        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            subject TEXT DEFAULT '',
            difficulty TEXT DEFAULT 'Easy',
            created_by INTEGER,
            created_by_type TEXT DEFAULT 'mentor',
            created_date TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'published'
        );

        CREATE TABLE IF NOT EXISTS questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            difficulty TEXT DEFAULT 'Easy',
            explanation TEXT DEFAULT '',
            FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS quiz_results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            marks INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            accuracy REAL DEFAULT 0.0,
            topic TEXT DEFAULT '',
            difficulty TEXT DEFAULT '',
            time_taken INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Pass',
            date TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
        );

        CREATE TABLE IF NOT EXISTS violations (
            violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            warning_count INTEGER DEFAULT 0,
            date TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
        );

        CREATE TABLE IF NOT EXISTS student_streaks (
            streak_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE,
            current_streak INTEGER DEFAULT 0,
            longest_streak INTEGER DEFAULT 0,
            last_quiz_date TEXT,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );

        CREATE TABLE IF NOT EXISTS badges (
            badge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            mentor_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT DEFAULT '🏆',
            description TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (mentor_id) REFERENCES mentors(mentor_id)
        );

        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            mentor_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            comment TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (mentor_id) REFERENCES mentors(mentor_id)
        );

        CREATE TABLE IF NOT EXISTS access_codes (
            code_id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            code TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL CHECK(type IN ('primary','backup')),
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','used','expired','disabled')),
            max_attempts INTEGER DEFAULT 1,
            start_date TEXT,
            start_time TEXT,
            expiry_date TEXT,
            expiry_time TEXT,
            created_date TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
        );

        CREATE TABLE IF NOT EXISTS code_usage_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            attempt_type TEXT NOT NULL,
            used_at TEXT DEFAULT (datetime('now')),
            status TEXT DEFAULT 'success',
            FOREIGN KEY (code_id) REFERENCES access_codes(code_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
        );
    """)

    # Migration: add status column to quizzes if missing
    try:
        cursor.execute("ALTER TABLE quizzes ADD COLUMN status TEXT DEFAULT 'published'")
    except sqlite3.OperationalError:
        pass

    # Migration: add source column to violations
    try:
        cursor.execute("ALTER TABLE violations ADD COLUMN source TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    # Migration: add student_code column to students
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN student_code TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass

    # Assign codes to existing students without one
    rows = cursor.execute("SELECT student_id FROM students WHERE student_code IS NULL OR student_code = ''").fetchall()
    if rows:
        for idx, row in enumerate(rows):
            code = f"APLS{idx + 1:03d}"
            cursor.execute("UPDATE students SET student_code = ? WHERE student_id = ?", (code, row["student_id"]))

    # Migration: study_materials table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_materials (
                material_id INTEGER PRIMARY KEY AUTOINCREMENT,
                mentor_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                course TEXT DEFAULT '',
                category TEXT DEFAULT '',
                file_type TEXT DEFAULT '',
                file_path TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                external_link TEXT DEFAULT '',
                link_type TEXT DEFAULT '',
                visibility TEXT DEFAULT 'public' CHECK(visibility IN ('public','private')),
                total_downloads INTEGER DEFAULT 0,
                total_views INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active' CHECK(status IN ('active','hidden')),
                created_date TEXT DEFAULT (datetime('now')),
                updated_date TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (mentor_id) REFERENCES mentors(mentor_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Migration: announcements table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                created_by INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                active INTEGER DEFAULT 1
            )
        """)
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scorecards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                cert_id TEXT UNIQUE NOT NULL,
                score REAL,
                accuracy REAL,
                mentor_name TEXT,
                generated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Migration: add status/approved_by/approved_at to mentors
    try:
        cursor.execute("ALTER TABLE mentors ADD COLUMN status TEXT DEFAULT 'active'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE mentors ADD COLUMN approved_by INTEGER NULL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE mentors ADD COLUMN approved_at TEXT NULL")
    except sqlite3.OperationalError:
        pass

    # Fix: set NULL status to 'active' for existing mentors
    cursor.execute("UPDATE mentors SET status = 'active' WHERE status IS NULL")

    # Insert default admin if not exists
    cursor.execute("SELECT * FROM admins WHERE email = ?", ("admin@system.com",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO admins (email, password) VALUES (?, ?)",
            ("admin@system.com", hashlib.sha256("admin123".encode()).hexdigest()),
        )

    conn.commit()
    conn.close()


def seed_sample_data():
    conn = get_db()
    cursor = conn.cursor()

    def fix_password(table, column, email, plain_password):
        h = hashlib.sha256(plain_password.encode()).hexdigest()
        cursor.execute(
            f"UPDATE {table} SET {column} = ? WHERE email = ? AND length({column}) < 40",
            (h, email),
        )

    fix_password("students", "password", "student@system.com", "student123")
    fix_password("mentors", "password", "mentor@system.com", "mentor123")
    fix_password("admins", "password", "admin@system.com", "admin123")

    cursor.execute("SELECT * FROM mentors WHERE email = ?", ("mentor@system.com",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO mentors (mentor_name, email, password, subject) VALUES (?, ?, ?, ?)",
            ("Dr. Smith", "mentor@system.com", hashlib.sha256("mentor123".encode()).hexdigest(), "Computer Science"),
        )

    # Get or create sample student
    cursor.execute("SELECT * FROM students WHERE email = ?", ("student@system.com",))
    if not cursor.fetchone():
        sc = generate_student_code(conn)
        cursor.execute(
            "INSERT INTO students (name, email, password, course, student_code) VALUES (?, ?, ?, ?, ?)",
            ("Rahul Sharma", "student@system.com", hashlib.sha256("student123".encode()).hexdigest(), "Computer Science", sc),
        )

    # ─── Indian Students Data Generator ─────────────────────────────
    existing_results = cursor.execute("SELECT COUNT(*) FROM quiz_results").fetchone()[0]
    if existing_results > 0:
        conn.close()
        return

    INDIAN_FIRST = ["Aarav","Vivaan","Aditya","Vihaan","Arjun","Sai","Reyansh","Ayaan","Ishaan","Dhruv","Ananya","Riya","Shreya","Priya","Sneha","Aisha","Isha","Maya","Neha","Kavya","Rohan","Amit","Vikas","Sunil","Kiran","Rajesh","Deepak","Manoj","Sanjay","Vijay","Pooja","Anjali","Divya","Swati","Komal","Ritu","Nisha","Geeta","Meena","Rekha","Arjun","Karan","Rahul","Ankit","Varun","Nikhil","Siddharth","Pranav","Harsh","Yash"]
    INDIAN_LAST = ["Sharma","Verma","Patel","Gupta","Reddy","Singh","Kumar","Jain","Mehta","Shah","Desai","Joshi","Pandey","Mishra","Agarwal","Rao","Choudhary","Nair","Iyer","Menon","Bose","Sen","Das","Ghosh","Roy","Sarkar","Banerjee","Chakraborty","Mukherjee","Dasgupta","Naik","Pawar","Patil","Deshmukh","Kulkarni","Wagh","More","Sawant","Mahajan","Gokhale"]
    COURSES = ["Computer Science","Information Technology","Data Science","Artificial Intelligence","Electronics Engineering","Mechanical Engineering","Civil Engineering","Electrical Engineering","Business Administration","Commerce","Economics","Mathematics","Physics","Chemistry","Biology","Biotechnology","Pharmacy","Nursing","Law","English Literature"]
    QUIZ_TOPICS = [("Machine Learning Basics","Computer Science","Medium"),("Human Digestive System","Science","Easy"),("Data Structures & Algorithms","Computer Science","Hard"),("Photosynthesis & Plant Biology","Science","Easy"),("Linear Algebra","Mathematics","Medium"),("World History: WW2","History","Hard"),("Python Programming","Computer Science","Easy"),("Calculus Fundamentals","Mathematics","Hard"),("Quantum Physics Intro","Physics","Hard"),("English Grammar","Language","Easy"),("Database Management Systems","Computer Science","Medium"),("Organic Chemistry","Chemistry","Hard"),("Cell Biology","Biology","Medium"),("Macroeconomics","Economics","Easy"),("Fluid Mechanics","Mechanical Engineering","Hard")]

    # Create quizzes
    quiz_ids = []
    for topic, subject, diff in QUIZ_TOPICS:
        cursor.execute(
            "INSERT INTO quizzes (topic, subject, difficulty, created_by, created_by_type, status) VALUES (?, ?, ?, 1, 'mentor', 'published')",
            (topic, subject, diff),
        )
        quiz_ids.append(cursor.lastrowid)

    for qid in quiz_ids:
        for i in range(5):
            cursor.execute(
                "INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (qid, f"Question {i+1}", "Option A", "Option B", "Option C", "Option D", "A", ["Easy","Medium","Hard","Easy","Medium"][i]),
            )

    # Create 50 Indian students
    used_names = set()
    used_emails = set()
    student_ids = []

    for i in range(50):
        fname = random.choice(INDIAN_FIRST)
        lname = random.choice(INDIAN_LAST)
        name = f"{fname} {lname}"
        while name in used_names:
            fname = random.choice(INDIAN_FIRST)
            lname = random.choice(INDIAN_LAST)
            name = f"{fname} {lname}"
        used_names.add(name)
        email = f"{fname.lower()}.{lname.lower()}{i}@gmail.com"
        while email in used_emails:
            email = f"{fname.lower()}.{lname.lower()}{random.randint(10,99)}@gmail.com"
        used_emails.add(email)
        pwd_hash = hashlib.sha256("student123".encode()).hexdigest()
        course = random.choice(COURSES)
        code = generate_student_code(conn)
        reg_date = (datetime.now() - timedelta(days=random.randint(10, 90))).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO students (name, email, password, course, registration_date, student_code) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, pwd_hash, course, reg_date, code),
        )
        student_ids.append(cursor.lastrowid)

    date_pool = [(datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d %H:%M:%S") for d in range(45)]

    for sid in student_ids:
        num_quizzes = random.randint(4, 10)
        selected = random.sample(quiz_ids, min(num_quizzes, len(quiz_ids)))
        for qid in selected:
            total = 5
            base = random.uniform(0.2, 0.95)
            marks = max(0, min(total, round(base * total)))
            accuracy = round((marks / total) * 100, 2)
            status = "Pass" if accuracy >= 40 else "Fail"
            time_taken = random.randint(3, 20)
            diff = random.choice(["Easy", "Medium", "Hard"])
            dt = random.choice(date_pool)
            topic_row = cursor.execute("SELECT topic FROM quizzes WHERE quiz_id=?", (qid,)).fetchone()
            cursor.execute(
                "INSERT INTO quiz_results (student_id, quiz_id, marks, total_questions, accuracy, topic, difficulty, time_taken, status, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, qid, marks, total, accuracy, topic_row["topic"], diff, time_taken, status, dt),
            )

    for sid in student_ids:
        current = random.randint(0, 15)
        longest = max(current, random.randint(1, 20))
        last = (datetime.now() - timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d")
        cursor.execute(
            "INSERT INTO student_streaks (student_id, current_streak, longest_streak, last_quiz_date) VALUES (?, ?, ?, ?)",
            (sid, current, longest, last),
        )

    BADGE_NAMES = ["Star Performer","Quick Learner","Consistent Scholar","Top Scorer","Improvement Star","Dedicated Learner","Subject Expert","Rising Star"]
    BADGE_ICONS = ["⭐","🚀","📚","🏆","📈","🔥","🎯","💡"]
    for sid in random.sample(student_ids, 30):
        for _ in range(random.randint(1, 3)):
            idx = random.randint(0, len(BADGE_NAMES)-1)
            q = random.choice(QUIZ_TOPICS)
            cursor.execute(
                "INSERT INTO badges (student_id, mentor_id, badge_name, badge_icon, description) VALUES (?, 1, ?, ?, ?)",
                (sid, BADGE_NAMES[idx], BADGE_ICONS[idx], f"Excellent in {q[0]}"),
            )

    FEEDBACK = ["Great improvement!","Needs to focus on fundamentals.","Excellent analytical skills.","Consistent performer.","Good progress, more practice needed.","Deep understanding of concepts.","Work on time management.","Outstanding performance!","Regular study pays off.","Has potential to be top performer."]
    for sid in random.sample(student_ids, 40):
        rating = random.randint(2, 5)
        comment = random.choice(FEEDBACK)
        days = random.randint(1, 30)
        dt = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO feedback (student_id, mentor_id, rating, comment, created_at) VALUES (?, 1, ?, ?, ?)",
            (sid, rating, comment, dt),
        )

    for sid in random.sample(student_ids, 20):
        for _ in range(random.randint(1, 2)):
            qid = random.choice(quiz_ids)
            days = random.randint(1, 20)
            dt = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO violations (student_id, quiz_id, warning_count, date, source) VALUES (?, ?, ?, ?, 'tab_switch')",
                (sid, qid, random.randint(1, 3), dt),
            )

    conn.commit()
    conn.close()
    print("[Seed] 50 Indian students + 15 quizzes + results, streaks, badges, feedback, violations created.")


# ═════════════════════════════════════════════════════════════════════
# DEMO DSA QUIZ SEEDER (auto-creates on server start)
# ═════════════════════════════════════════════════════════════════════

def seed_demo_dsa_quiz():
    """Creates a DSA quiz by Dr. Smith with 10 real questions, 40 students,
       realistic attempts (including cheaters), and a special multi-use access code."""
    conn = get_db()
    c = conn.cursor()

    # Check if already seeded
    existing = c.execute("SELECT quiz_id FROM quizzes WHERE topic = 'DSA Comprehensive Assessment'").fetchone()
    if existing:
        quiz_id = existing["quiz_id"]
        # Ensure the special access code exists
        ac_exists = c.execute("SELECT code_id FROM access_codes WHERE code = 'DEMO2026'").fetchone()
        if not ac_exists:
            c.execute("INSERT INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, 'DEMO2026', 'primary', 'active', 9999)", (quiz_id,))
            conn.commit()
            print("[Seed] Created special access code: DEMO2026")
        conn.close()
        return

    # ── Get Mentor (Dr. Smith) ──
    mentor = c.execute("SELECT mentor_id FROM mentors WHERE email = 'mentor@system.com'").fetchone()
    if not mentor:
        conn.close()
        return
    mentor_id = mentor["mentor_id"]

    # ── Create Quiz ──
    c.execute("INSERT INTO quizzes (topic, subject, difficulty, created_by, created_by_type, status) VALUES (?, ?, ?, ?, 'mentor', 'published')",
              ("DSA Comprehensive Assessment", "Computer Science", "Mixed", mentor_id))
    quiz_id = c.lastrowid

    # ── 10 Real DSA Questions ──
    questions = [
        ("What is the time complexity of binary search on a sorted array?", "O(log n)", "O(n)", "O(n log n)", "O(1)", "A", "Easy"),
        ("Which data structure uses FIFO principle?", "Stack", "Queue", "Binary Tree", "Hash Table", "B", "Easy"),
        ("What is the worst-case time complexity of Quick Sort?", "O(n log n)", "O(n)", "O(n^2)", "O(log n)", "C", "Medium"),
        ("In a max-heap, the parent node is always __ than its children.", "Smaller", "Equal", "Greater", "Unrelated", "C", "Medium"),
        ("Which traversal of a BST gives elements in sorted order?", "Pre-order", "Post-order", "In-order", "Level-order", "C", "Easy"),
        ("What is the space complexity of Merge Sort?", "O(1)", "O(log n)", "O(n)", "O(n^2)", "C", "Medium"),
        ("Which is NOT a self-balancing BST?", "AVL Tree", "Red-Black Tree", "B-Tree", "Binary Search Tree", "D", "Medium"),
        ("Dijkstra's algorithm finds __ in a weighted graph.", "MST", "Shortest Path", "Max Flow", "SCC", "B", "Hard"),
        ("Amortized time complexity of push in dynamic array?", "O(n)", "O(log n)", "O(1)", "O(n^2)", "C", "Hard"),
        ("'Overlapping subproblems' in DP means?", "Same subproblem solved multiple times", "No optimal substructure", "Cannot be divided", "Single solution", "A", "Hard"),
    ]
    for q in questions:
        c.execute("INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty) VALUES (?,?,?,?,?,?,?,?)",
                  (quiz_id, q[0], q[1], q[2], q[3], q[4], q[5], q[6]))

    # ── Special Multi-Use Access Code ──
    special_code = "DEMO2026"
    c.execute("INSERT INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, ?, 'primary', 'active', 9999)",
              (quiz_id, special_code))

    # ── 40 Students ──
    FIRST = ["Aarav","Vivaan","Aditya","Vihaan","Arjun","Sai","Reyansh","Ayaan","Ishaan","Dhruv",
             "Ananya","Riya","Shreya","Priya","Sneha","Aisha","Isha","Maya","Neha","Kavya",
             "Rohan","Amit","Vikas","Sunil","Kiran","Rajesh","Deepak","Manoj","Sanjay","Vijay",
             "Pooja","Anjali","Divya","Swati","Komal","Ritu","Nisha","Geeta","Meena","Rekha"]
    LAST = ["Sharma","Verma","Patel","Gupta","Reddy","Singh","Kumar","Jain","Mehta","Shah",
            "Desai","Joshi","Pandey","Mishra","Agarwal","Rao","Choudhary","Nair","Iyer","Menon",
            "Bose","Sen","Das","Ghosh","Roy","Sarkar","Banerjee","Chakraborty","Mukherjee","Dasgupta",
            "Naik","Pawar","Patil","Deshmukh","Kulkarni","Wagh","More","Sawant","Mahajan","Gokhale"]
    COURSES = ["Computer Science","Information Technology","Data Science","AI & ML","Electronics"]
    pwd = hashlib.sha256("student123".encode()).hexdigest()

    student_ids = []
    used_names = set()
    for i in range(40):
        while True:
            fn = FIRST[i % len(FIRST)]
            ln = LAST[i % len(LAST)]
            name = f"{fn} {ln}"
            if name not in used_names:
                used_names.add(name)
                break
            fn, ln = random.choice(FIRST), random.choice(LAST)
            name = f"{fn} {ln}"
            if name not in used_names:
                used_names.add(name)
                break

        email = f"{fn.lower()}.{ln.lower()}{i+1}@gmail.com"
        sc = generate_student_code(conn)
        reg = (datetime.now() - timedelta(days=random.randint(15, 90))).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO students (name, email, password, course, registration_date, student_code) VALUES (?,?,?,?,?,?)",
                  (name, email, pwd, random.choice(COURSES), reg, sc))
        student_ids.append(c.lastrowid)

    # ── Realistic Quiz Attempts ──
    # Pattern: (num_students, min_marks, max_marks, min_time, max_time, has_violations, violation_sources)
    patterns = [
        (6, 8, 10, 80, 180, False, None),       # toppers
        (10, 6, 8, 100, 240, False, None),       # good
        (12, 4, 6, 120, 300, False, None),       # average
        (5, 1, 4, 60, 200, False, None),         # weak
        (3, 9, 10, 12, 35, True, "tab_switch,devtools,tab_switch,print_screen,copy_paste"),  # cheaters (fast + suspicious)
        (2, 7, 9, 50, 120, True, "tab_switch,tab_switch,window_blur"),  # tab cheaters
        (2, 2, 5, 300, 500, False, None),        # very slow / disengaged
    ]

    date_pool = [(datetime.now() - timedelta(days=d, hours=random.randint(0,12))).strftime("%Y-%m-%d %H:%M:%S") for d in range(1, 31)]
    sidx = 0
    for min_m, max_m, min_t, max_t, has_cheat, v_src in [(p[1],p[2],p[3],p[4],p[5],p[6]) for p in patterns for _ in range(p[0])]:
        if sidx >= len(student_ids):
            break
        sid = student_ids[sidx]
        sidx += 1
        marks = random.randint(min_m, max_m)
        acc = round(marks / 10 * 100, 1)
        status = "Pass" if acc >= 40 else "Fail"
        tt = random.randint(min_t, max_t)
        dt = random.choice(date_pool)

        c.execute("INSERT INTO quiz_results (student_id, quiz_id, marks, total_questions, accuracy, topic, difficulty, time_taken, status, date) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (sid, quiz_id, marks, 10, acc, "DSA Comprehensive Assessment", "Mixed", tt, status, dt))

        if has_cheat and v_src:
            sources = v_src.split(",")
            c.execute("INSERT INTO violations (student_id, quiz_id, warning_count, date, source) VALUES (?,?,?,?,?)",
                      (sid, quiz_id, len(sources), dt, v_src))

    # Streaks
    for sid in student_ids:
        cur = random.randint(0, 15)
        lng = max(cur, random.randint(1, 20))
        last_d = (datetime.now() - timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d")
        c.execute("INSERT INTO student_streaks (student_id, current_streak, longest_streak, last_quiz_date) VALUES (?,?,?,?)",
                  (sid, cur, lng, last_d))

    conn.commit()
    conn.close()
    print(f"[Seed] DSA Demo Quiz created — Access Code: {special_code}")


def seed_demo_scorecards():
    """Create sample scorecards for demo data."""
    conn = get_db()
    c = conn.cursor()
    existing = c.execute("SELECT id FROM scorecards LIMIT 1").fetchone()
    if existing:
        conn.close()
        return
    results = c.execute(
        "SELECT qr.student_id, qr.quiz_id, qr.accuracy, m.mentor_name "
        "FROM quiz_results qr "
        "JOIN quizzes q ON qr.quiz_id = q.quiz_id "
        "JOIN mentors m ON q.created_by = m.mentor_id "
        "ORDER BY qr.accuracy DESC LIMIT 5"
    ).fetchall()
    if not results:
        conn.close()
        return
    import uuid
    for r in results:
        cid = "CERT-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()
        c.execute(
            "INSERT INTO scorecards (student_id, quiz_id, cert_id, score, accuracy, mentor_name) VALUES (?,?,?,?,?,?)",
            (r["student_id"], r["quiz_id"], cid, r["accuracy"], r["accuracy"], r["mentor_name"]),
        )
    conn.commit()
    conn.close()
    print(f"[Seed] Demo scorecards created for certificate verification")


def generate_student_code(db):
    """Generate next student code in format APLS001, APLS002, etc."""
    last = db.execute(
        "SELECT student_code FROM students WHERE student_code != '' ORDER BY student_code DESC LIMIT 1"
    ).fetchone()
    if last and last["student_code"]:
        num = int(last["student_code"].replace("APLS", "")) + 1
    else:
        num = 1
    return f"APLS{num:03d}"


import secrets
import string

def generate_access_code():
    """Generate a unique 8-character alphanumeric access code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))


def seed_demo_student_results():
    """Give the demo student (student@system.com) realistic quiz results
    across multiple topics so the Exam Coach and dashboards have real data."""
    conn = get_db()
    c = conn.cursor()

    student = c.execute("SELECT student_id FROM students WHERE email = 'student@system.com'").fetchone()
    if not student:
        conn.close()
        return
    sid = student["student_id"]

    existing = c.execute("SELECT COUNT(*) as cnt FROM quiz_results WHERE student_id = ?", (sid,)).fetchone()["cnt"]
    if existing >= 8:
        conn.close()
        return

    if existing > 0:
        c.execute("DELETE FROM quiz_results WHERE student_id = ?", (sid,))
        c.execute("DELETE FROM violations WHERE student_id = ?", (sid,))
        c.execute("DELETE FROM student_streaks WHERE student_id = ?", (sid,))
        c.execute("DELETE FROM badges WHERE student_id = ?", (sid,))

    topics = [
        ("Python Programming", "Computer Science", "Easy", 85, 45),
        ("Data Structures & Algorithms", "Computer Science", "Hard", 60, 90),
        ("Machine Learning Basics", "Computer Science", "Medium", 72, 65),
        ("Database Management Systems", "Computer Science", "Medium", 78, 55),
        ("Linear Algebra", "Mathematics", "Medium", 55, 75),
        ("Calculus Fundamentals", "Mathematics", "Hard", 45, 110),
        ("Human Digestive System", "Science", "Easy", 90, 30),
        ("Cell Biology", "Biology", "Medium", 65, 60),
        ("English Grammar", "Language", "Easy", 88, 25),
        ("Organic Chemistry", "Chemistry", "Hard", 40, 100),
    ]

    quiz_ids = []
    for topic, subject, diff, _, _ in topics:
        existing_q = c.execute("SELECT quiz_id FROM quizzes WHERE topic = ? AND subject = ?", (topic, subject)).fetchone()
        if existing_q:
            quiz_ids.append(existing_q["quiz_id"])
        else:
            c.execute(
                "INSERT INTO quizzes (topic, subject, difficulty, created_by, created_by_type, status) VALUES (?, ?, ?, 1, 'mentor', 'published')",
                (topic, subject, diff),
            )
            qid = c.lastrowid
            for i in range(5):
                c.execute(
                    "INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (qid, f"Q{i+1} on {topic}", "Option A", "Option B", "Option C", "Option D", "A", diff),
                )
            quiz_ids.append(qid)

    now = datetime.now()
    for i, (topic, subject, diff, base_acc, base_time) in enumerate(topics):
        days_ago = 30 - (i * 3)
        dt = (now - timedelta(days=days_ago, hours=random.randint(8, 20))).strftime("%Y-%m-%d %H:%M:%S")
        total = 5
        variation = random.uniform(-8, 8)
        accuracy = max(10, min(100, base_acc + variation))
        marks = max(1, min(total, round(accuracy / 100 * total)))
        accuracy = round((marks / total) * 100, 1)
        time_var = random.randint(-10, 15)
        time_taken = max(10, base_time + time_var)
        status = "Pass" if accuracy >= 40 else "Fail"

        c.execute(
            "INSERT INTO quiz_results (student_id, quiz_id, marks, total_questions, accuracy, topic, difficulty, time_taken, status, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (sid, quiz_ids[i], marks, total, accuracy, topic, diff, time_taken, status, dt),
        )

    c.execute(
        "INSERT OR REPLACE INTO student_streaks (student_id, current_streak, longest_streak, last_quiz_date) VALUES (?, ?, ?, ?)",
        (sid, 5, 12, now.strftime("%Y-%m-%d")),
    )

    c.execute("INSERT INTO violations (student_id, quiz_id, warning_count, date, source) VALUES (?, ?, ?, ?, ?)",
              (sid, quiz_ids[1], 2, (now - timedelta(days=24)).strftime("%Y-%m-%d %H:%M:%S"), "tab_switch,window_blur"))

    badges = [
        ("Python Pro", "🐍", "Scored 85%+ in Python Programming"),
        ("Science Star", "⭐", "Excellent in Human Digestive System"),
        ("Improvement Goal", "📈", "Showing consistent improvement"),
    ]
    for bname, icon, desc in badges:
        c.execute("INSERT INTO badges (student_id, mentor_id, badge_name, badge_icon, description) VALUES (?, 1, ?, ?, ?)",
                  (sid, bname, icon, desc))

    conn.commit()
    conn.close()
    print("[Seed] Demo student results created — 10 quizzes with realistic data")
