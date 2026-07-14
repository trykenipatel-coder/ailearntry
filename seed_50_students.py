"""
Seed 50 Indian students with realistic sample data.
Run: python seed_50_students.py
"""
import sqlite3
import hashlib
import random
from datetime import datetime, timedelta
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "learning_system.db")

INDIAN_FIRST = [
    "Aarav","Vivaan","Aditya","Vihaan","Arjun","Sai","Reyansh","Ayaan","Ishaan","Dhruv",
    "Ananya","Riya","Shreya","Priya","Sneha","Aisha","Isha","Maya","Neha","Kavya",
    "Rohan","Amit","Vikas","Sunil","Kiran","Rajesh","Deepak","Manoj","Sanjay","Vijay",
    "Pooja","Anjali","Divya","Swati","Komal","Ritu","Nisha","Geeta","Meena","Rekha",
    "Arjun","Karan","Rahul","Ankit","Varun","Nikhil","Siddharth","Pranav","Harsh","Yash"
]

INDIAN_LAST = [
    "Sharma","Verma","Patel","Gupta","Reddy","Singh","Kumar","Jain","Mehta","Shah",
    "Desai","Joshi","Pandey","Mishra","Agarwal","Rao","Choudhary","Nair","Iyer","Menon",
    "Bose","Sen","Das","Ghosh","Roy","Sarkar","Banerjee","Chakraborty","Mukherjee","Dasgupta",
    "Naik","Pawar","Patil","Deshmukh","Kulkarni","Wagh","More","Sawant","Mahajan","Gokhale"
]

COURSES = [
    "Computer Science", "Information Technology", "Data Science", "Artificial Intelligence",
    "Electronics Engineering", "Mechanical Engineering", "Civil Engineering", "Electrical Engineering",
    "Business Administration", "Commerce", "Economics", "Mathematics", "Physics", "Chemistry",
    "Biology", "Biotechnology", "Pharmacy", "Nursing", "Law", "English Literature"
]

QUIZ_TOPICS = [
    "Machine Learning Basics", "Human Digestive System", "Data Structures & Algorithms",
    "Photosynthesis & Plant Biology", "Linear Algebra", "World History: WW2",
    "Python Programming", "Calculus Fundamentals", "Quantum Physics Intro", "English Grammar"
]

def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get existing quizzes
    quizzes = cursor.execute("SELECT quiz_id, topic FROM quizzes").fetchall()
    if not quizzes:
        print("No quizzes found. Run the app first to seed sample data.")
        return

    # Get existing mentor
    mentor = cursor.execute("SELECT mentor_id FROM mentors LIMIT 1").fetchone()
    mentor_id = mentor[0] if mentor else 1

    # Generate 50 students
    used_names = set()
    used_emails = set()
    student_ids = []

    # Find max existing code
    last = cursor.execute("SELECT student_code FROM students WHERE student_code != '' ORDER BY student_code DESC LIMIT 1").fetchone()
    code_num = (int(last["student_code"].replace("APLS", "")) + 1) if last and last["student_code"] else 1

    for i in range(50):
        # Unique name
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
        reg_date = (datetime.now() - timedelta(days=random.randint(10, 90))).strftime("%Y-%m-%d %H:%M:%S")

        code = f"APLS{code_num:03d}"
        code_num += 1
        cursor.execute(
            "INSERT INTO students (name, email, password, course, registration_date, student_code) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, pwd_hash, course, reg_date, code),
        )
        student_ids.append(cursor.lastrowid)

    print(f"✅ Inserted {len(student_ids)} Indian students")

    # Seed quiz_results for each student
    date_pool = [(datetime.now() - timedelta(days=d)).strftime("%Y-%m-%d %H:%M:%S") for d in range(45)]
    result_count = 0

    for sid in student_ids:
        num_quizzes = random.randint(4, 10)
        selected = random.sample(list(quizzes), min(num_quizzes, len(quizzes)))

        for q in selected:
            qid, topic = q["quiz_id"], q["topic"]
            total = 5
            # Indian student performance: varied, some high some low
            base = random.uniform(0.2, 0.95)
            marks = max(0, min(total, round(base * total)))
            accuracy = round((marks / total) * 100, 2)
            status = "Pass" if accuracy >= 40 else "Fail"
            time_taken = random.randint(3, 20)
            diff = random.choice(["Easy", "Medium", "Hard"])
            dt = random.choice(date_pool)

            cursor.execute(
                """INSERT INTO quiz_results (student_id, quiz_id, marks, total_questions, accuracy, topic, difficulty, time_taken, status, date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sid, qid, marks, total, accuracy, topic, diff, time_taken, status, dt),
            )
            result_count += 1

    print(f"✅ Inserted {result_count} quiz results")

    # Seed streaks for each student
    for sid in student_ids:
        current = random.randint(0, 15)
        longest = max(current, random.randint(1, 20))
        last = (datetime.now() - timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d")

        cursor.execute(
            "INSERT INTO student_streaks (student_id, current_streak, longest_streak, last_quiz_date) VALUES (?, ?, ?, ?)",
            (sid, current, longest, last),
        )

    print("✅ Inserted streaks")

    # Seed badges (some students get badges)
    BADGE_NAMES = ["Star Performer", "Quick Learner", "Consistent Scholar", "Top Scorer",
                    "Improvement Star", "Dedicated Learner", "Subject Expert", "Rising Star"]
    BADGE_ICONS = ["⭐", "🚀", "📚", "🏆", "📈", "🔥", "🎯", "💡"]

    badge_count = 0
    for sid in random.sample(student_ids, 30):
        num_badges = random.randint(1, 3)
        for _ in range(num_badges):
            idx = random.randint(0, len(BADGE_NAMES)-1)
            cursor.execute(
                "INSERT INTO badges (student_id, mentor_id, badge_name, badge_icon, description) VALUES (?, ?, ?, ?, ?)",
                (sid, mentor_id, BADGE_NAMES[idx], BADGE_ICONS[idx],
                 f"Awarded for excellent performance in {random.choice(QUIZ_TOPICS)}"),
            )
            badge_count += 1

    print(f"✅ Inserted {badge_count} badges")

    # Seed mentor feedback
    FEEDBACK_COMMENTS = [
        "Great improvement in recent quizzes!", "Needs to focus on fundamentals.",
        "Excellent analytical skills.", "Consistent performer. Keep it up!",
        "Good progress but needs more practice.", "Shows deep understanding of concepts.",
        "Should work on time management.", "Outstanding performance this month.",
        "Regular study is showing results.", "Has potential to be a top performer.",
        "Needs guidance in advanced topics.", "Remarkable dedication to learning.",
    ]
    fb_count = 0
    for sid in random.sample(student_ids, 40):
        rating = random.randint(2, 5)
        comment = random.choice(FEEDBACK_COMMENTS)
        days_ago = random.randint(1, 30)
        dt = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            "INSERT INTO feedback (student_id, mentor_id, rating, comment, created_at) VALUES (?, ?, ?, ?, ?)",
            (sid, mentor_id, rating, comment, dt),
        )
        fb_count += 1

    print(f"✅ Inserted {fb_count} mentor feedbacks")

    # Seed violations (some students)
    violation_count = 0
    for sid in random.sample(student_ids, 15):
        num_violations = random.randint(1, 2)
        for _ in range(num_violations):
            q = random.choice(quizzes)
            days_ago = random.randint(1, 20)
            dt = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                "INSERT INTO violations (student_id, quiz_id, warning_count, date, source) VALUES (?, ?, ?, ?, ?)",
                (sid, q["quiz_id"], random.randint(1, 3), dt, "tab_switch"),
            )
            violation_count += 1

    print(f"✅ Inserted {violation_count} violations")

    conn.commit()
    conn.close()
    print("\n🎉 All 50 Indian student data seeded successfully!")
    print("   Login as mentor@system.com / mentor123 to view.")


if __name__ == "__main__":
    seed()
