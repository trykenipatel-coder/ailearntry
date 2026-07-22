import sqlite3
import hashlib
import random
import logging
from config import DATABASE_PATH
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
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

        CREATE TABLE IF NOT EXISTS question_attempts (
            attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            quiz_id INTEGER NOT NULL,
            topic TEXT DEFAULT '',
            difficulty TEXT DEFAULT '',
            is_correct INTEGER DEFAULT 0,
            response_time REAL DEFAULT 0.0,
            hint_used INTEGER DEFAULT 0,
            attempt_number INTEGER DEFAULT 1,
            confidence INTEGER DEFAULT NULL,
            als_score REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (question_id) REFERENCES questions(question_id),
            FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
        );

        CREATE TABLE IF NOT EXISTS topic_mastery (
            mastery_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            total_attempts INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            avg_response_time REAL DEFAULT 0.0,
            hint_count INTEGER DEFAULT 0,
            mastery_pct REAL DEFAULT 0.0,
            last_attempted TEXT DEFAULT (datetime('now')),
            UNIQUE(student_id, topic),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );
    """)

    # Migration: question_attempts table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS question_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                topic TEXT DEFAULT '',
                difficulty TEXT DEFAULT '',
                is_correct INTEGER DEFAULT 0,
                response_time REAL DEFAULT 0.0,
                hint_used INTEGER DEFAULT 0,
                attempt_number INTEGER DEFAULT 1,
                confidence INTEGER DEFAULT NULL,
                als_score REAL DEFAULT 0.0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (question_id) REFERENCES questions(question_id),
                FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Migration: topic_mastery table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_mastery (
                mastery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                total_attempts INTEGER DEFAULT 0,
                correct_count INTEGER DEFAULT 0,
                avg_response_time REAL DEFAULT 0.0,
                hint_count INTEGER DEFAULT 0,
                mastery_pct REAL DEFAULT 0.0,
                last_attempted TEXT DEFAULT (datetime('now')),
                UNIQUE(student_id, topic),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Personalized Revision Scheduler table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS revision_schedule (
                revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                priority_score REAL DEFAULT 0.0,
                next_revision_date TEXT,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending','completed','skipped')),
                mastery_at_revision REAL DEFAULT 0.0,
                estimated_minutes INTEGER DEFAULT 15,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(student_id, topic),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Explainable Recommendation Engine table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                recommendation_type TEXT NOT NULL,
                priority TEXT DEFAULT 'Medium' CHECK(priority IN ('High','Medium','Low')),
                reason TEXT NOT NULL,
                confidence TEXT DEFAULT 'Medium' CHECK(confidence IN ('High','Medium','Low')),
                accuracy_snapshot REAL DEFAULT 0.0,
                mastery_snapshot REAL DEFAULT 0.0,
                avg_time_snapshot REAL DEFAULT 0.0,
                wrong_attempts_snapshot INTEGER DEFAULT 0,
                estimated_minutes INTEGER DEFAULT 15,
                status TEXT DEFAULT 'active' CHECK(status IN ('active','completed','dismissed')),
                generated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Semester Learning Report table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS semester_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                semester TEXT DEFAULT 'Current',
                total_quizzes INTEGER DEFAULT 0,
                avg_score REAL DEFAULT 0.0,
                als_score REAL DEFAULT 0.0,
                total_time_seconds INTEGER DEFAULT 0,
                avg_response_time REAL DEFAULT 0.0,
                strong_topics TEXT DEFAULT '[]',
                weak_topics TEXT DEFAULT '[]',
                achievements TEXT DEFAULT '[]',
                recommendations TEXT DEFAULT '[]',
                improvement_pct REAL DEFAULT 0.0,
                generated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Adaptive Learning Passport table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_passports (
                passport_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER UNIQUE NOT NULL,
                learning_level TEXT DEFAULT 'Beginner' CHECK(learning_level IN ('Beginner','Intermediate','Advanced')),
                health_score REAL DEFAULT 50.0,
                total_achievements INTEGER DEFAULT 0,
                quiz_accuracy REAL DEFAULT 0.0,
                avg_response_time REAL DEFAULT 0.0,
                revision_streak INTEGER DEFAULT 0,
                topic_mastery_json TEXT DEFAULT '{}',
                progress_timeline TEXT DEFAULT '[]',
                last_updated TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Mentor Analytics Cache table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mentor_analytics_cache (
                cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
                mentor_id INTEGER NOT NULL,
                total_students INTEGER DEFAULT 0,
                avg_class_performance REAL DEFAULT 0.0,
                struggling_students TEXT DEFAULT '[]',
                top_students TEXT DEFAULT '[]',
                difficult_topics TEXT DEFAULT '[]',
                quiz_completion_rate REAL DEFAULT 0.0,
                last_computed TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (mentor_id) REFERENCES mentors(mentor_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Interventions table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interventions (
                intervention_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                mentor_id INTEGER NOT NULL,
                intervention_type TEXT NOT NULL CHECK(intervention_type IN ('Quiz','Revision','Material','Reminder','Meeting')),
                topic TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                priority TEXT DEFAULT 'Medium' CHECK(priority IN ('High','Medium','Low')),
                status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending','In Progress','Completed','Cancelled')),
                deadline TEXT DEFAULT '',
                assigned_date TEXT DEFAULT (datetime('now')),
                completion_date TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (mentor_id) REFERENCES mentors(mentor_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Coding Challenges table
    # Resource History table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resource_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                platform TEXT DEFAULT '',
                category TEXT DEFAULT '',
                opened_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Favorite Resources table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorite_resources (
                fav_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                platform TEXT DEFAULT '',
                category TEXT DEFAULT '',
                added_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                UNIQUE(student_id, topic, platform)
            )
        """)
    except sqlite3.OperationalError:
        pass

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

    # Proctoring Sessions table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proctoring_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                face_verified INTEGER DEFAULT 0,
                id_verified INTEGER DEFAULT 0,
                face_registered INTEGER DEFAULT 0,
                id_photo_url TEXT DEFAULT '',
                face_photo_url TEXT DEFAULT '',
                risk_level TEXT DEFAULT 'low',
                total_events INTEGER DEFAULT 0,
                warnings_count INTEGER DEFAULT 0,
                started_at TEXT DEFAULT (datetime('now')),
                ended_at TEXT NULL,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (quiz_id) REFERENCES quizzes(quiz_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Camera Events table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS camera_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT DEFAULT 'low',
                screenshot_url TEXT DEFAULT '',
                confidence_score REAL DEFAULT 0.0,
                description TEXT DEFAULT '',
                device_info TEXT DEFAULT '',
                status TEXT DEFAULT 'open',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES proctoring_sessions(session_id)
            )
        """)
    except sqlite3.OperationalError:
        pass

    # Proctoring Reports table
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proctoring_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                quiz_id INTEGER NOT NULL,
                student_name TEXT DEFAULT '',
                quiz_title TEXT DEFAULT '',
                exam_date TEXT DEFAULT '',
                face_verification_status TEXT DEFAULT 'pending',
                id_verification_status TEXT DEFAULT 'pending',
                total_events INTEGER DEFAULT 0,
                high_risk_count INTEGER DEFAULT 0,
                medium_risk_count INTEGER DEFAULT 0,
                low_risk_count INTEGER DEFAULT 0,
                risk_level TEXT DEFAULT 'low',
                mentor_remarks TEXT DEFAULT '',
                final_action TEXT DEFAULT 'pending',
                generated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (session_id) REFERENCES proctoring_sessions(session_id)
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

    # Ensure demo admin exists with correct password
    h_admin = hashlib.sha256("admin123".encode()).hexdigest()
    cursor.execute("SELECT admin_id FROM admins WHERE email = ?", ("admin@system.com",))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO admins (email, password) VALUES (?, ?)", ("admin@system.com", h_admin))
    else:
        cursor.execute("UPDATE admins SET password = ? WHERE email = ?", (h_admin, "admin@system.com"))

    # Ensure demo mentor exists with correct password
    h_mentor = hashlib.sha256("mentor123".encode()).hexdigest()
    cursor.execute("SELECT mentor_id FROM mentors WHERE email = ?", ("mentor@system.com",))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO mentors (mentor_name, email, password, subject, status) VALUES (?, ?, ?, ?, 'active')",
                       ("Dr. Smith", "mentor@system.com", h_mentor, "Computer Science"))
    else:
        cursor.execute("UPDATE mentors SET password = ?, status = 'active' WHERE email = ?", (h_mentor, "mentor@system.com"))

    # Ensure demo student exists with correct password
    h_student = hashlib.sha256("student123".encode()).hexdigest()
    cursor.execute("SELECT student_id FROM students WHERE email = ?", ("student@system.com",))
    if not cursor.fetchone():
        sc = f"APLS{cursor.execute('SELECT COUNT(*) FROM students').fetchone()[0] + 1:03d}"
        cursor.execute("INSERT INTO students (name, email, password, course, student_code) VALUES (?, ?, ?, ?, ?)",
                       ("Rahul Sharma", "student@system.com", h_student, "Computer Science", sc))
    else:
        cursor.execute("UPDATE students SET password = ? WHERE email = ?", (h_student, "student@system.com"))

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
        conn.commit()
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

    # ── Create access codes for all seed quizzes ──
    for qid in quiz_ids:
        code = generate_access_code()
        cursor.execute(
            "INSERT OR IGNORE INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, ?, 'primary', 'active', 9999)",
            (qid, code),
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
            c.execute("INSERT OR IGNORE INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, 'DEMO2026', 'primary', 'active', 9999)", (quiz_id,))
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
    c.execute("INSERT OR IGNORE INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, ?, 'primary', 'active', 9999)",
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

        email = f"{fn.lower()}.{ln.lower()}dsa{i+1}@demo.com"
        sc = generate_student_code(conn)
        reg = (datetime.now() - timedelta(days=random.randint(15, 90))).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT OR IGNORE INTO students (name, email, password, course, registration_date, student_code) VALUES (?,?,?,?,?,?)",
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
    if existing >= 10:
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


# ═════════════════════════════════════════════════════════════════════
# DEMO PYTHON QUIZ SEEDER (auto-creates on server start)
# ═════════════════════════════════════════════════════════════════════

def seed_demo_python_quiz():
    """Creates a Python Programming quiz by Dr. Smith with 10 real questions,
       15 student attempts, and DEMO2026 access code (unlimited)."""
    conn = get_db()
    c = conn.cursor()

    existing = c.execute("SELECT quiz_id FROM quizzes WHERE topic = 'Python Programming Basics'").fetchone()
    if existing:
        quiz_id = existing["quiz_id"]
        ac_exists = c.execute("SELECT code_id FROM access_codes WHERE code = 'DEMO2026' AND quiz_id = ?", (quiz_id,)).fetchone()
        if not ac_exists:
            c.execute("INSERT OR IGNORE INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, 'DEMO2026', 'primary', 'active', 9999)", (quiz_id,))
            conn.commit()
            print("[Seed] Created DEMO2026 for Python quiz")
        conn.close()
        return

    mentor = c.execute("SELECT mentor_id FROM mentors WHERE email = 'mentor@system.com'").fetchone()
    if not mentor:
        conn.close()
        return
    mentor_id = mentor["mentor_id"]

    c.execute("INSERT INTO quizzes (topic, subject, difficulty, created_by, created_by_type, status) VALUES (?, ?, ?, ?, 'mentor', 'published')",
              ("Python Programming Basics", "Computer Science", "Easy", mentor_id))
    quiz_id = c.lastrowid

    questions = [
        ("What does the `len()` function return for a string?", "Number of characters", "Number of words", "Last character", "First character", "A", "Easy"),
        ("Which keyword is used to define a function in Python?", "func", "def", "function", "define", "B", "Easy"),
        ("What is the output of `print(type(3.14))`?", "<class 'int'>", "<class 'float'>", "<class 'str'>", "<class 'decimal'>", "B", "Easy"),
        ("Which data type is immutable in Python?", "List", "Dictionary", "Set", "Tuple", "D", "Medium"),
        ("What does `range(5)` generate?", "0,1,2,3,4", "1,2,3,4,5", "0,1,2,3,4,5", "1,2,3,4", "A", "Easy"),
        ("How do you start a for loop in Python?", "for i in range(5)", "for(i=0;i<5;i++)", "foreach i in 5", "loop i in 5", "A", "Easy"),
        ("What is the correct file extension for Python files?", ".python", ".py", ".pt", ".pyt", "B", "Easy"),
        ("Which operator is used for exponentiation in Python?", "^", "**", "exp", "^^", "B", "Medium"),
        ("What does `append()` do to a list?", "Removes last element", "Adds element to end", "Sorts the list", "Reverses the list", "B", "Easy"),
        ("What is the output of `print(2 ** 3)`?", "6", "8", "5", "23", "B", "Medium"),
    ]
    for q in questions:
        c.execute("INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty) VALUES (?,?,?,?,?,?,?,?)",
                  (quiz_id, q[0], q[1], q[2], q[3], q[4], q[5], q[6]))

    c.execute("INSERT OR IGNORE INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, 'DEMO2026', 'primary', 'active', 9999)", (quiz_id,))

    FIRST = ["Aarav","Vivaan","Aditya","Vihaan","Arjun","Ananya","Riya","Shreya","Priya","Sneha",
             "Rohan","Amit","Vikas","Kiran","Rajesh"]
    LAST = ["Sharma","Verma","Patel","Gupta","Singh","Kumar","Jain","Mehta","Shah","Desai",
            "Joshi","Pandey","Mishra","Agarwal","Rao"]
    pwd = hashlib.sha256("student123".encode()).hexdigest()
    student_ids = []
    used_names = set()
    for i in range(15):
        fn = FIRST[i % len(FIRST)]
        ln = LAST[i % len(LAST)]
        name = f"{fn} {ln}"
        if name in used_names:
            fn, ln = random.choice(FIRST), random.choice(LAST)
            name = f"{fn} {ln}"
        used_names.add(name)
        email = f"{fn.lower()}.{ln.lower()}py{i+1}@demo.com"
        sc = generate_student_code(conn)
        reg = (datetime.now() - timedelta(days=random.randint(10, 60))).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT OR IGNORE INTO students (name, email, password, course, registration_date, student_code) VALUES (?,?,?,?,?,?)",
                  (name, email, pwd, "Computer Science", reg, sc))
        student_ids.append(c.lastrowid)

    date_pool = [(datetime.now() - timedelta(days=d, hours=random.randint(0,12))).strftime("%Y-%m-%d %H:%M:%S") for d in range(1, 30)]
    patterns = [
        (3, 9, 10, 30, 80),
        (5, 7, 8, 40, 120),
        (4, 5, 6, 50, 150),
        (3, 2, 4, 20, 60),
    ]
    sidx = 0
    for cnt, min_m, max_m, min_t, max_t in patterns:
        for _ in range(cnt):
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
                      (sid, quiz_id, marks, 10, acc, "Python Programming Basics", "Easy", tt, status, dt))

    for sid in student_ids:
        cur = random.randint(1, 8)
        lng = max(cur, random.randint(2, 12))
        last_d = (datetime.now() - timedelta(days=random.randint(0, 3))).strftime("%Y-%m-%d")
        c.execute("INSERT INTO student_streaks (student_id, current_streak, longest_streak, last_quiz_date) VALUES (?,?,?,?)",
                  (sid, cur, lng, last_d))

    conn.commit()
    conn.close()
    print(f"[Seed] Python Demo Quiz created — Access Code: DEMO2026")


def seed_python_basics_quiz():
    """Creates a 5-question Python Basics quiz with DEMO2026 access code."""
    conn = get_db()
    c = conn.cursor()

    existing = c.execute("SELECT quiz_id FROM quizzes WHERE topic = 'Python Basics'").fetchone()
    if existing:
        quiz_id = existing["quiz_id"]
        ac_exists = c.execute("SELECT code_id FROM access_codes WHERE code = 'DEMO2026' AND quiz_id = ?", (quiz_id,)).fetchone()
        if not ac_exists:
            c.execute("INSERT OR IGNORE INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, 'DEMO2026', 'primary', 'active', 9999)", (quiz_id,))
            conn.commit()
        conn.close()
        return

    mentor = c.execute("SELECT mentor_id FROM mentors WHERE email = 'mentor@system.com'").fetchone()
    if not mentor:
        conn.close()
        return
    mentor_id = mentor["mentor_id"]

    c.execute("INSERT INTO quizzes (topic, subject, difficulty, created_by, created_by_type, status) VALUES (?, ?, ?, ?, 'mentor', 'published')",
              ("Python Basics", "Computer Science", "Easy", mentor_id))
    quiz_id = c.lastrowid

    questions = [
        ("What is the output of print(type('hello'))?", "<class 'str'>", "<class 'int'>", "<class 'char'>", "<class 'string'>", "A", "Easy"),
        ("Which of the following is used to create a list in Python?", "{}", "[]", "()", "<>", "B", "Easy"),
        ("What is the correct syntax to print 'Hello World' in Python?", "echo 'Hello World'", "print('Hello World')", "console.log('Hello World')", "printf('Hello World')", "B", "Easy"),
        ("Which method adds an element to the end of a list?", "add()", "insert()", "append()", "push()", "C", "Easy"),
        ("What will be the output of: x = [1,2,3]; print(len(x))?", "2", "3", "6", "Error", "B", "Easy"),
    ]
    for q in questions:
        c.execute("INSERT INTO questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, difficulty) VALUES (?,?,?,?,?,?,?,?)",
                  (quiz_id, q[0], q[1], q[2], q[3], q[4], q[5], q[6]))

    c.execute("INSERT OR IGNORE INTO access_codes (quiz_id, code, type, status, max_attempts) VALUES (?, 'DEMO2026', 'primary', 'active', 9999)", (quiz_id,))

    conn.commit()
    conn.close()
    print(f"[Seed] Python Basics Quiz (5 questions) created — Access Code: DEMO2026")


# ═══════════════════════════════════════════════════════════════════════
# ADAPTIVE LEARNING DEMO DATA SEEDER
# ═══════════════════════════════════════════════════════════════════════

def seed_adaptive_demo_data():
    """Create realistic adaptive learning data for student@system.com
    so the analytics dashboard has data to show immediately.
    Uses whatever quizzes exist in the DB — no hardcoded topics."""
    conn = get_db()
    c = conn.cursor()

    student = c.execute("SELECT student_id FROM students WHERE email = 'student@system.com'").fetchone()
    if not student:
        print("[Seed] WARNING: student@system.com not found, skipping adaptive seed")
        conn.close()
        return
    sid = student["student_id"]

    existing = c.execute("SELECT COUNT(*) as cnt FROM question_attempts WHERE student_id=?", (sid,)).fetchone()["cnt"]
    if existing > 0:
        conn.close()
        return

    all_quizzes = c.execute("SELECT quiz_id, topic FROM quizzes WHERE status='published'").fetchall()
    if not all_quizzes:
        print("[Seed] WARNING: No published quizzes found, skipping adaptive seed")
        conn.close()
        return

    all_questions = c.execute("SELECT question_id, quiz_id, difficulty FROM questions").fetchall()
    if not all_questions:
        print("[Seed] WARNING: No questions found, skipping adaptive seed")
        conn.close()
        return

    qid_to_quiz = {q["question_id"]: q["quiz_id"] for q in all_questions}

    quiz_topics = {}
    for qz in all_quizzes:
        quiz_topics[qz["topic"]] = qz["quiz_id"]

    questions_by_quiz = {}
    for q in all_questions:
        if q["quiz_id"] not in questions_by_quiz:
            questions_by_quiz[q["quiz_id"]] = []
        questions_by_quiz[q["quiz_id"]].append(q)

    difficulties = ["Easy", "Medium", "Hard"]

    for topic_name, qid in quiz_topics.items():
        mastery = random.uniform(30, 85)
        total_attempts = random.randint(8, 25)
        correct_count = int(total_attempts * mastery / 100)
        avg_time = random.uniform(15, 45)
        last_attempted = (datetime.now() - timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d %H:%M:%S")
        try:
            c.execute(
                """INSERT OR IGNORE INTO topic_mastery
                   (student_id, topic, total_attempts, correct_count, avg_response_time,
                    hint_count, mastery_pct, last_attempted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, topic_name, total_attempts, correct_count, round(avg_time, 1),
                 random.randint(0, 3), round(mastery, 1), last_attempted)
            )
        except Exception as e:
            print(f"[Seed] topic_mastery insert error: {e}")

    for day_offset in range(15):
        dt = (datetime.now() - timedelta(days=15 - day_offset, hours=random.randint(8, 20))).strftime("%Y-%m-%d %H:%M:%S")
        progress_factor = 0.4 + (day_offset / 15) * 0.5
        num_questions = random.randint(3, 6)

        available = [q for q in all_questions if q["quiz_id"] in questions_by_quiz]
        if not available:
            continue

        chosen = random.sample(available, min(num_questions, len(available)))

        for q in chosen:
            is_correct = 1 if random.random() < (progress_factor * 0.8 + 0.1) else 0
            response_time = random.uniform(10, 50) if is_correct else random.uniform(20, 60)
            hint_used = 1 if random.random() < 0.15 else 0
            quiz_id = q["quiz_id"]
            topic_name = ""
            for t, qid_val in quiz_topics.items():
                if qid_val == quiz_id:
                    topic_name = t
                    break

            try:
                c.execute(
                    """INSERT INTO question_attempts
                       (student_id, question_id, quiz_id, topic, difficulty, is_correct,
                        response_time, hint_used, attempt_number, confidence, als_score, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, NULL, 0, ?)""",
                    (sid, q["question_id"], quiz_id, topic_name, q["difficulty"],
                     is_correct, round(response_time, 1), hint_used, dt)
                )
            except Exception as e:
                print(f"[Seed] question_attempts insert error: {e}")

    print(f"[Seed] Adaptive demo data created for student@system.com ({len(all_quizzes)} quizzes, {len(all_questions)} questions available)")


# ═══════════════════════════════════════════════════════════════════════
# PRS + ERE DEMO DATA SEEDER
# Creates topic_mastery and question_attempts for Revision Schedule
# and Explainable Recommendations features.
# ═══════════════════════════════════════════════════════════════════════

def seed_prs_ere_demo_data():
    """Create realistic topic_mastery and question_attempts for student@system.com
    specifically designed to produce rich PRS and ERE results.

    Uses hardcoded scenarios to guarantee diverse outputs:
    - Some topics with very low mastery (high revision priority)
    - Some topics with high mastery (skip revision)
    - Some topics with slow response times
    - Some topics with many wrong attempts
    """
    conn = get_db()
    c = conn.cursor()

    student = c.execute("SELECT student_id FROM students WHERE email = 'student@system.com'").fetchone()
    if not student:
        print("[Seed] PRS/ERE: student@system.com not found, skipping")
        conn.close()
        return
    sid = student["student_id"]

    existing = c.execute("SELECT COUNT(*) as cnt FROM topic_mastery WHERE student_id=?", (sid,)).fetchone()["cnt"]
    if existing >= 6:
        conn.close()
        return

    if existing > 0:
        c.execute("DELETE FROM topic_mastery WHERE student_id=?", (sid,))
        c.execute("DELETE FROM question_attempts WHERE student_id=?", (sid,))

    all_quizzes = c.execute("SELECT quiz_id, topic FROM quizzes WHERE status='published'").fetchall()
    if not all_quizzes:
        print("[Seed] PRS/ERE: No published quizzes found")
        conn.close()
        return

    all_questions = c.execute("SELECT question_id, quiz_id, difficulty FROM questions").fetchall()
    if not all_questions:
        print("[Seed] PRS/ERE: No questions found")
        conn.close()
        return

    quiz_topics = {q["topic"]: q["quiz_id"] for q in all_quizzes}
    questions_by_quiz = {}
    for q in all_questions:
        questions_by_quiz.setdefault(q["quiz_id"], []).append(q)

    scenarios = [
        {"topic": None, "mastery": 34, "total": 20, "correct": 7, "avg_time": 72, "hints": 5, "days_ago": 10},
        {"topic": None, "mastery": 48, "total": 18, "correct": 9, "avg_time": 55, "hints": 3, "days_ago": 8},
        {"topic": None, "mastery": 62, "total": 15, "correct": 9, "avg_time": 40, "hints": 2, "days_ago": 5},
        {"topic": None, "mastery": 88, "total": 12, "correct": 11, "avg_time": 22, "hints": 0, "days_ago": 3},
        {"topic": None, "mastery": 95, "total": 10, "correct": 10, "avg_time": 18, "hints": 0, "days_ago": 2},
        {"topic": None, "mastery": 42, "total": 22, "correct": 9, "avg_time": 65, "hints": 4, "days_ago": 12},
        {"topic": None, "mastery": 72, "total": 14, "correct": 10, "avg_time": 35, "hints": 1, "days_ago": 4},
        {"topic": None, "mastery": 28, "total": 25, "correct": 7, "avg_time": 78, "hints": 6, "days_ago": 15},
    ]

    topic_list = list(quiz_topics.keys())
    random.shuffle(topic_list)

    for i, sc in enumerate(scenarios):
        if i >= len(topic_list):
            break
        topic_name = topic_list[i]
        quiz_id = quiz_topics[topic_name]
        last_dt = (datetime.now() - timedelta(days=sc["days_ago"], hours=random.randint(8, 20))).strftime("%Y-%m-%d %H:%M:%S")

        try:
            c.execute(
                """INSERT OR REPLACE INTO topic_mastery
                   (student_id, topic, total_attempts, correct_count, avg_response_time,
                    hint_count, mastery_pct, last_attempted)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, topic_name, sc["total"], sc["correct"], sc["avg_time"],
                 sc["hints"], sc["mastery"], last_dt)
            )
        except Exception as e:
            print(f"[Seed] PRS/ERE topic_mastery error: {e}")

        quiz_questions = questions_by_quiz.get(quiz_id, [])
        if not quiz_questions:
            continue

        wrong_count = sc["total"] - sc["correct"]
        total_to_insert = sc["total"]

        for q_idx in range(min(total_to_insert, len(quiz_questions))):
            q = quiz_questions[q_idx % len(quiz_questions)]
            day_offset = random.randint(0, sc["days_ago"])
            q_dt = (datetime.now() - timedelta(days=day_offset, hours=random.randint(8, 20))).strftime("%Y-%m-%d %H:%M:%S")
            is_correct = 1 if q_idx < sc["correct"] else 0
            response_time = sc["avg_time"] + random.uniform(-15, 15)
            if response_time < 5:
                response_time = 5
            hint_used = 1 if q_idx < sc["hints"] else 0

            try:
                c.execute(
                    """INSERT INTO question_attempts
                       (student_id, question_id, quiz_id, topic, difficulty, is_correct,
                        response_time, hint_used, attempt_number, confidence, als_score, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, NULL, 0, ?)""",
                    (sid, q["question_id"], quiz_id, topic_name, q["difficulty"],
                     is_correct, round(response_time, 1), hint_used, q_dt)
                )
            except Exception:
                pass

    conn.commit()
    conn.close()
    print(f"[Seed] PRS/ERE demo data created for student@system.com ({len(scenarios)} topics with varied scenarios)")


def seed_demo_interventions():
    """Create sample interventions for demo mentor."""
    conn = get_db()
    try:
        existing = conn.execute("SELECT COUNT(*) as cnt FROM interventions").fetchone()[0]
        if existing > 0:
            return

        mentor = conn.execute("SELECT mentor_id FROM mentors LIMIT 1").fetchone()
        if not mentor:
            return
        mid = mentor[0]

        students = conn.execute("SELECT student_id, name FROM students LIMIT 6").fetchall()
        if not students:
            return

        interventions = [
            (students[0][0], mid, "Quiz", "OOP Concepts", "Scored below 40% on OOP quiz — needs practice", "High", "Pending", "2026-07-20"),
            (students[0][0], mid, "Revision", "Database Design", "Weak topic — mastery at 28%", "High", "In Progress", "2026-07-22"),
            (students[1][0], mid, "Material", "Data Structures", "Average score 45% — needs supplementary material", "Medium", "Pending", "2026-07-25"),
            (students[1][0], mid, "Meeting", "General", "Low participation — only 2 quizzes attempted", "Medium", "Pending", "2026-07-21"),
            (students[2][0], mid, "Quiz", "Algorithms", "Struggling with recursion topics", "Low", "Completed", "2026-07-15"),
            (students[3][0], mid, "Revision", "Python Basics", "Response time too high — needs timed practice", "Medium", "In Progress", "2026-07-23"),
            (students[4][0], mid, "Reminder", "Web Development", "Missed last 2 quiz deadlines", "Low", "Pending", "2026-07-28"),
            (students[5][0], mid, "Quiz", "Machine Learning", "New student — baseline assessment needed", "High", "Pending", "2026-07-19"),
        ]

        for item in interventions:
            conn.execute(
                """INSERT OR IGNORE INTO interventions
                   (student_id, mentor_id, intervention_type, topic, reason, priority, status, deadline, assigned_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                item
            )

        conn.commit()
        print("[Seed] Demo interventions created")
    except Exception as e:
        print(f"[Seed] Demo interventions error: {e}")
    finally:
        conn.close()


