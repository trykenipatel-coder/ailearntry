"""
Adaptive Learning Engine - Core Module
======================================
Research-oriented Adaptive Learning Engine that dynamically selects
questions based on multiple student performance factors.

Uses a weighted Adaptive Learning Score (ALS) formula:
ALS = (0.40 × Accuracy) + (0.25 × Response Time Score) + (0.20 × Topic Mastery)
    + (0.10 × Streak Score) + (0.05 × Hint Usage Score)

Based on ALS:
- ALS >= 85: Hard question from weakest topic
- ALS 70-84: Medium question from weakest/current topic
- ALS < 70: Easy question focusing on weak concepts
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from database import get_db


class AdaptiveLearningEngine:
    """
    Research-oriented Adaptive Learning Engine that dynamically selects
    questions based on multiple student performance factors.

    Uses a weighted Adaptive Learning Score (ALS) formula:
    ALS = (0.40 × Accuracy) + (0.25 × Response Time Score) + (0.20 × Topic Mastery)
        + (0.10 × Streak Score) + (0.05 × Hint Usage Score)

    Based on ALS:
    - ALS >= 85: Hard question from weakest topic
    - ALS 70-84: Medium question from weakest/current topic
    - ALS < 70: Easy question focusing on weak concepts
    """

    def __init__(self, db_path=None):
        self.db_path = db_path

    def calculate_als(self, student_id, quiz_id):
        """
        Calculate the Adaptive Learning Score (ALS) for a student.

        The ALS is a composite score (0-100) derived from five weighted factors:
        - Accuracy (40%): Recent correct answer rate
        - Response Time (25%): Speed of correct answers relative to baseline
        - Topic Mastery (20%): Average mastery across all topics
        - Streak (10%): Current correct answer streak
        - Hint Usage (5%): Inverse of hint dependency

        Args:
            student_id: The student's unique identifier
            quiz_id: The current quiz identifier

        Returns:
            dict: ALS score breakdown including difficulty level and topic info
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            # 1. Accuracy (0.40 weight) - from recent attempts
            recent_attempts = conn.execute("""
                SELECT is_correct FROM question_attempts
                WHERE student_id=? ORDER BY created_at DESC LIMIT 10
            """, (student_id,)).fetchall()
            correct_count = sum(1 for a in recent_attempts if a['is_correct'])
            accuracy = (correct_count / max(len(recent_attempts), 1)) * 100
            accuracy_score = accuracy  # 0-100

            # 2. Response Time Score (0.25 weight)
            time_data = conn.execute("""
                SELECT AVG(response_time) as avg_time,
                       AVG(CASE WHEN is_correct THEN response_time END) as correct_time
                FROM question_attempts WHERE student_id=? AND quiz_id=?
            """, (student_id, quiz_id)).fetchone()
            avg_time = time_data['avg_time'] if time_data and time_data['avg_time'] else 30
            # Faster correct answers = higher score (normalized 0-100)
            expected_time = 30  # seconds per question baseline
            time_score = max(0, min(100, (expected_time / max(avg_time, 1)) * 100))

            # 3. Topic Mastery (0.20 weight) - average across all topics
            mastery = conn.execute("""
                SELECT AVG(mastery_pct) as avg_mastery FROM topic_mastery WHERE student_id=?
            """, (student_id,)).fetchone()
            mastery_score = mastery['avg_mastery'] if mastery and mastery['avg_mastery'] else 50

            # 4. Streak Score (0.10 weight)
            streak_data = conn.execute("""
                SELECT current_streak FROM student_streaks WHERE student_id=?
            """, (student_id,)).fetchone()
            streak = streak_data['current_streak'] if streak_data else 0
            streak_score = min(100, streak * 15)  # Each correct adds 15, caps at 100

            # 5. Hint Usage Score (0.05 weight) - less hints = higher score
            hint_data = conn.execute("""
                SELECT COUNT(CASE WHEN hint_used=1 THEN 1 END) as hints, COUNT(*) as total
                FROM question_attempts WHERE student_id=? AND quiz_id=?
            """, (student_id, quiz_id)).fetchone()
            hint_pct = (hint_data['hints'] / max(hint_data['total'], 1)) * 100
            hint_score = 100 - hint_pct  # Less hints = higher score

            # Calculate composite ALS
            als = (0.40 * accuracy_score) + (0.25 * time_score) + (0.20 * mastery_score) + \
                  (0.10 * streak_score) + (0.05 * hint_score)

            # Determine difficulty level
            if als >= 85:
                difficulty_level = 'Hard'
            elif als >= 70:
                difficulty_level = 'Medium'
            else:
                difficulty_level = 'Easy'

            return {
                'als': round(als, 2),
                'accuracy_score': round(accuracy_score, 2),
                'time_score': round(time_score, 2),
                'mastery_score': round(mastery_score, 2),
                'streak_score': round(streak_score, 2),
                'hint_score': round(hint_score, 2),
                'difficulty_level': difficulty_level,
                'weak_topics': self.get_weakest_topics(student_id, 3),
                'strong_topics': self.get_strongest_topics(student_id, 3)
            }

        except Exception as e:
            print(f"Error calculating ALS: {e}")
            return {
                'als': 50.0,
                'accuracy_score': 50.0,
                'time_score': 50.0,
                'mastery_score': 50.0,
                'streak_score': 0.0,
                'hint_score': 100.0,
                'difficulty_level': 'Medium',
                'weak_topics': [],
                'strong_topics': []
            }
        finally:
            conn.close()

    def get_topic_mastery(self, student_id, topic):
        """
        Get mastery level for a specific topic.

        Args:
            student_id: The student's unique identifier
            topic: The topic name

        Returns:
            dict: Topic mastery data with mastery_pct, attempts, etc.
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            mastery = conn.execute("""
                SELECT * FROM topic_mastery WHERE student_id=? AND topic=?
            """, (student_id, topic)).fetchone()

            if mastery:
                return {
                    'topic': mastery['topic'],
                    'mastery_pct': mastery['mastery_pct'],
                    'total_attempts': mastery['total_attempts'],
                    'correct_count': mastery['correct_count'],
                    'avg_response_time': mastery['avg_response_time'],
                    'hint_count': mastery['hint_count'],
                    'last_practiced': mastery['last_practiced']
                }
            else:
                return {
                    'topic': topic,
                    'mastery_pct': 0.0,
                    'total_attempts': 0,
                    'correct_count': 0,
                    'avg_response_time': 0.0,
                    'hint_count': 0,
                    'last_practiced': None
                }

        except Exception as e:
            print(f"Error getting topic mastery: {e}")
            return {
                'topic': topic,
                'mastery_pct': 0.0,
                'total_attempts': 0,
                'correct_count': 0,
                'avg_response_time': 0.0,
                'hint_count': 0,
                'last_practiced': None
            }
        finally:
            conn.close()

    def get_weakest_topics(self, student_id, limit=3):
        """
        Get the student's weakest topics sorted by lowest mastery.

        Args:
            student_id: The student's unique identifier
            limit: Maximum number of topics to return

        Returns:
            list: List of weakest topics with mastery data
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            topics = conn.execute("""
                SELECT topic, mastery_pct, total_attempts, correct_count
                FROM topic_mastery
                WHERE student_id=? AND total_attempts > 0
                ORDER BY mastery_pct ASC
                LIMIT ?
            """, (student_id, limit)).fetchall()

            return [
                {
                    'topic': t['topic'],
                    'mastery_pct': t['mastery_pct'],
                    'total_attempts': t['total_attempts'],
                    'correct_count': t['correct_count']
                }
                for t in topics
            ]

        except Exception as e:
            print(f"Error getting weakest topics: {e}")
            return []
        finally:
            conn.close()

    def get_strongest_topics(self, student_id, limit=3):
        """
        Get the student's strongest topics sorted by highest mastery.

        Args:
            student_id: The student's unique identifier
            limit: Maximum number of topics to return

        Returns:
            list: List of strongest topics with mastery data
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            topics = conn.execute("""
                SELECT topic, mastery_pct, total_attempts, correct_count
                FROM topic_mastery
                WHERE student_id=? AND total_attempts > 0
                ORDER BY mastery_pct DESC
                LIMIT ?
            """, (student_id, limit)).fetchall()

            return [
                {
                    'topic': t['topic'],
                    'mastery_pct': t['mastery_pct'],
                    'total_attempts': t['total_attempts'],
                    'correct_count': t['correct_count']
                }
                for t in topics
            ]

        except Exception as e:
            print(f"Error getting strongest topics: {e}")
            return []
        finally:
            conn.close()

    def select_next_question(self, student_id, quiz_id, answered_question_ids):
        """
        Main adaptive question selection method.

        Selection logic:
        1. Calculate ALS to determine target difficulty
        2. Query questions matching target difficulty (excluding already answered)
        3. Fall back to any available difficulty if target not available
        4. Return selected question with explanation

        Args:
            student_id: The student's unique identifier
            quiz_id: The current quiz identifier
            answered_question_ids: List of question IDs already answered

        Returns:
            dict: Selected question with metadata and explanation, or None
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            # Step 1: Calculate ALS
            als_data = self.calculate_als(student_id, quiz_id)
            target_difficulty = als_data['difficulty_level']

            # Step 2: Build the list of answered IDs for exclusion
            excluded_ids = answered_question_ids if answered_question_ids else []

            # Step 3: Try to find a question with target difficulty
            question = None

            params = [quiz_id, target_difficulty]
            if excluded_ids:
                exclude_placeholders = ','.join(['?' for _ in excluded_ids])
                params += excluded_ids
                query = f"""
                    SELECT q.*
                    FROM questions q
                    WHERE q.quiz_id=? AND q.difficulty=? AND q.question_id NOT IN ({exclude_placeholders})
                    ORDER BY RANDOM() LIMIT 1
                """
            else:
                query = """
                    SELECT q.*
                    FROM questions q
                    WHERE q.quiz_id=? AND q.difficulty=?
                    ORDER BY RANDOM() LIMIT 1
                """
            question = conn.execute(query, params).fetchone()

            # Step 4: If no question with target difficulty, try any available
            if not question:
                params = [quiz_id]
                if excluded_ids:
                    exclude_placeholders = ','.join(['?' for _ in excluded_ids])
                    params += excluded_ids
                    query = f"""
                        SELECT q.*
                        FROM questions q
                        WHERE q.quiz_id=? AND q.question_id NOT IN ({exclude_placeholders})
                        ORDER BY RANDOM() LIMIT 1
                    """
                else:
                    query = """
                        SELECT q.*
                        FROM questions q
                        WHERE q.quiz_id=?
                        ORDER BY RANDOM() LIMIT 1
                    """
                question = conn.execute(query, params).fetchone()

            # Step 5: If no question exists at all
            if not question:
                return None

            # Get quiz topic
            quiz_row = conn.execute("SELECT topic FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            selected_topic = quiz_row['topic'] if quiz_row else "General"

            # Step 6: Get mastery for selected topic
            topic_mastery = self.get_topic_mastery(student_id, selected_topic)

            # Step 7: Build explanation
            explanation = self.get_explanation(
                student_id, quiz_id,
                {
                    'topic': selected_topic,
                    'difficulty': question['difficulty'],
                    'question_id': question['question_id']
                },
                als_data['als'],
                als_data
            )

            # Get total questions count
            total_row = conn.execute("SELECT COUNT(*) as cnt FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()
            total_questions = total_row['cnt'] if total_row else 0

            return {
                'question_id': question['question_id'],
                'question_text': question['question_text'],
                'option_a': question['option_a'],
                'option_b': question['option_b'],
                'option_c': question['option_c'],
                'option_d': question['option_d'],
                'correct_answer': question['correct_answer'],
                'difficulty': question['difficulty'],
                'topic': selected_topic,
                'explanation': explanation,
                'als_data': als_data,
                'total': total_questions,
            }

        except Exception as e:
            print(f"Error selecting next question: {e}")
            return None
        finally:
            conn.close()

    def record_attempt(self, student_id, question_id, quiz_id, topic, difficulty,
                       is_correct, response_time, hint_used=False, attempt_number=1,
                       confidence=None):
        """
        Record a question attempt and update all related metrics.

        This method:
        1. Inserts the attempt into question_attempts table
        2. Updates topic mastery for the student
        3. Updates the student's answer streak
        4. Updates the quiz score if applicable

        Args:
            student_id: The student's unique identifier
            question_id: The question that was answered
            quiz_id: The current quiz identifier
            topic: The topic of the question
            difficulty: The difficulty level
            is_correct: Whether the answer was correct
            response_time: Time taken to answer in seconds
            hint_used: Whether a hint was used
            attempt_number: Which attempt this is (1st, 2nd, etc.)
            confidence: Student's self-reported confidence (optional)

        Returns:
            dict: Result of the recording operation
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            # 1. Insert the attempt
            conn.execute("""
                INSERT INTO question_attempts
                (student_id, question_id, quiz_id, topic, difficulty, is_correct,
                 response_time, hint_used, attempt_number, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (student_id, question_id, quiz_id, topic, difficulty,
                  1 if is_correct else 0, response_time, 1 if hint_used else 0,
                  attempt_number, confidence, datetime.now().isoformat()))

            conn.commit()

            # 2. Update topic mastery
            self.update_topic_mastery(student_id, topic, is_correct, response_time)

            # 3. Update streak
            streak_data = conn.execute("""
                SELECT * FROM student_streaks WHERE student_id=?
            """, (student_id,)).fetchone()

            if is_correct:
                new_streak = (streak_data['current_streak'] + 1) if streak_data else 1
                longest_streak = max(
                    streak_data['longest_streak'] if streak_data else 0,
                    new_streak
                )
            else:
                new_streak = 0
                longest_streak = streak_data['longest_streak'] if streak_data else 0

            if streak_data:
                conn.execute("""
                    UPDATE student_streaks
                    SET current_streak=?, longest_streak=?, last_updated=?
                    WHERE student_id=?
                """, (new_streak, longest_streak, datetime.now().isoformat(), student_id))
            else:
                conn.execute("""
                    INSERT INTO student_streaks
                    (student_id, current_streak, longest_streak, last_updated)
                    VALUES (?, ?, ?, ?)
                """, (student_id, new_streak, longest_streak, datetime.now().isoformat()))

            conn.commit()

            # 4. Update quiz score
            quiz_stats = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) as correct
                FROM question_attempts
                WHERE student_id=? AND quiz_id=?
            """, (student_id, quiz_id)).fetchone()

            if quiz_stats:
                score_pct = (quiz_stats['correct'] / max(quiz_stats['total'], 1)) * 100
                conn.execute("""
                    INSERT OR REPLACE INTO quiz_scores
                    (student_id, quiz_id, score, total_questions, completed, last_updated)
                    VALUES (?, ?, ?, ?, 1, ?)
                """, (student_id, quiz_id, score_pct, quiz_stats['total'],
                      datetime.now().isoformat()))
                conn.commit()

            return {
                'success': True,
                'is_correct': is_correct,
                'current_streak': new_streak,
                'longest_streak': longest_streak,
                'quiz_score': score_pct if quiz_stats else 0
            }

        except Exception as e:
            print(f"Error recording attempt: {e}")
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def update_topic_mastery(self, student_id, topic, is_correct, response_time):
        """
        Update mastery level for a specific topic after a question attempt.

        Mastery formula:
        - mastery_pct = (correct_count / total_attempts) * 100 * time_factor
        - time_factor = min(1.5, expected_time / actual_time) for correct answers
        - time_factor = 1.0 for incorrect answers

        Args:
            student_id: The student's unique identifier
            topic: The topic to update
            is_correct: Whether the answer was correct
            response_time: Time taken to answer in seconds
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            existing = conn.execute("""
                SELECT * FROM topic_mastery WHERE student_id=? AND topic=?
            """, (student_id, topic)).fetchone()

            expected_time = 30  # baseline seconds

            if existing:
                new_total = existing['total_attempts'] + 1
                new_correct = existing['correct_count'] + (1 if is_correct else 0)

                # Update average response time
                old_avg = existing['avg_response_time'] or 0
                old_total = existing['total_attempts'] or 0
                new_avg_time = ((old_avg * old_total) + response_time) / new_total

                new_hint_count = existing['hint_count']

                # Calculate new mastery percentage
                accuracy_pct = (new_correct / max(new_total, 1)) * 100
                if is_correct:
                    time_factor = min(1.5, expected_time / max(response_time, 1))
                else:
                    time_factor = 1.0
                mastery_pct = accuracy_pct * time_factor

                conn.execute("""
                    UPDATE topic_mastery
                    SET total_attempts=?, correct_count=?, avg_response_time=?,
                        hint_count=?, mastery_pct=?, last_practiced=?
                    WHERE student_id=? AND topic=?
                """, (new_total, new_correct, new_avg_time, new_hint_count,
                      mastery_pct, datetime.now().isoformat(), student_id, topic))
            else:
                new_total = 1
                new_correct = 1 if is_correct else 0
                if is_correct:
                    time_factor = min(1.5, expected_time / max(response_time, 1))
                else:
                    time_factor = 1.0
                mastery_pct = ((new_correct / max(new_total, 1)) * 100) * time_factor

                conn.execute("""
                    INSERT INTO topic_mastery
                    (student_id, topic, total_attempts, correct_count, avg_response_time,
                     hint_count, mastery_pct, last_practiced)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """, (student_id, topic, new_total, new_correct, response_time,
                      mastery_pct, datetime.now().isoformat()))

            conn.commit()

        except Exception as e:
            print(f"Error updating topic mastery: {e}")
        finally:
            conn.close()

    def get_explanation(self, student_id, quiz_id, selected_question, als_score, factors):
        """
        Generate a structured explanation for why a question was selected.

        Provides transparency into the adaptive selection process,
        explaining each factor that influenced the decision.

        Args:
            student_id: The student's unique identifier
            quiz_id: The current quiz identifier
            selected_question: Dict with question metadata (topic, difficulty, question_id)
            als_score: The calculated ALS score
            factors: Dict with individual ALS factor scores

        Returns:
            dict: Structured explanation with reasons and recommendation
        """
        topic = selected_question['topic']
        difficulty = selected_question['difficulty']
        accuracy = factors.get('accuracy_score', 0)
        time_score = factors.get('time_score', 0)
        mastery_score = factors.get('mastery_score', 0)
        streak_score = factors.get('streak_score', 0)
        hint_score = factors.get('hint_score', 0)

        # Get topic mastery for explanation
        topic_mastery = self.get_topic_mastery(student_id, topic)
        topic_mastery_pct = topic_mastery['mastery_pct']

        # Get streak
        conn = get_db()
        conn.row_factory = sqlite3.Row
        try:
            streak_data = conn.execute("""
                SELECT current_streak FROM student_streaks WHERE student_id=?
            """, (student_id,)).fetchone()
            streak = streak_data['current_streak'] if streak_data else 0
        except Exception:
            streak = 0
        finally:
            conn.close()

        # Determine response time label
        if time_score > 70:
            time_label = 'Fast'
        elif time_score > 40:
            time_label = 'Average'
        else:
            time_label = 'Slow'

        # Determine mastery label
        if topic_mastery_pct >= 80:
            mastery_label = 'Strong'
        elif topic_mastery_pct >= 50:
            mastery_label = 'Moderate'
        else:
            mastery_label = 'Weak'

        # Build reasons list
        reasons = [
            f"Your accuracy: {accuracy}%",
            f"Response time: {time_label}",
            f"Mastery in {topic}: {topic_mastery_pct}% ({mastery_label})",
            f"Current streak: {streak} correct answers",
            f"ALS Score: {als_score}/100 → Target difficulty: {difficulty}"
        ]

        # Add factor-specific insights
        if accuracy >= 80:
            reasons.append("High accuracy indicates strong understanding - challenging you further")
        elif accuracy < 50:
            reasons.append("Lower accuracy detected - focusing on foundational concepts")

        if hint_score < 50:
            reasons.append("Frequent hint usage noted - providing a more accessible question")

        # Generate recommendation
        weak_topics = self.get_weakest_topics(student_id, 2)
        if weak_topics:
            weak_names = [t['topic'] for t in weak_topics]
            recommendation = (
                f"Focus on your weakest topics ({', '.join(weak_names)}) "
                f"to improve overall performance."
            )
        else:
            recommendation = "Continue practicing to build topic mastery across all areas."

        return {
            "selected_difficulty": difficulty,
            "selected_topic": topic,
            "reasons": reasons,
            "recommendation": recommendation,
            "factor_breakdown": {
                "accuracy": {"score": accuracy, "weight": "40%"},
                "response_time": {"score": time_score, "weight": "25%"},
                "topic_mastery": {"score": mastery_score, "weight": "20%"},
                "streak": {"score": streak_score, "weight": "10%"},
                "hint_usage": {"score": hint_score, "weight": "5%"}
            }
        }

    def get_learning_analytics(self, student_id):
        """
        Get comprehensive learning analytics for the student dashboard.

        Provides a full picture of the student's learning journey including
        accuracy, topic mastery, difficulty progression, learning curve,
        and improvement trends.

        Args:
            student_id: The student's unique identifier

        Returns:
            dict: Comprehensive analytics data
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            # Overall accuracy
            overall = conn.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) as correct,
                       AVG(response_time) as avg_time
                FROM question_attempts WHERE student_id=?
            """, (student_id,)).fetchone()

            total_questions = overall['total'] if overall else 0
            correct_count = overall['correct'] if overall else 0
            overall_accuracy = (correct_count / max(total_questions, 1)) * 100
            avg_response_time = overall['avg_time'] if overall and overall['avg_time'] else 0

            # Topic mastery
            topics = conn.execute("""
                SELECT topic, mastery_pct, total_attempts, correct_count,
                       avg_response_time, hint_count, last_attempted
                FROM topic_mastery
                WHERE student_id=? AND total_attempts > 0
                ORDER BY mastery_pct DESC
            """, (student_id,)).fetchall()

            topic_mastery = [
                {
                    'topic': t['topic'],
                    'mastery_pct': t['mastery_pct'],
                    'total_attempts': t['total_attempts'],
                    'correct_count': t['correct_count'],
                    'avg_response_time': t['avg_response_time'],
                    'hint_count': t['hint_count'],
                    'last_attempted': t['last_attempted']
                }
                for t in topics
            ]

            # Weak and strong topics
            weak_topics = [
                {'topic': t['topic'], 'mastery_pct': t['mastery_pct']}
                for t in self.get_weakest_topics(student_id, 3)
            ]
            strong_topics = [
                {'topic': t['topic'], 'mastery_pct': t['mastery_pct']}
                for t in self.get_strongest_topics(student_id, 3)
            ]

            # Difficulty progression
            difficulty_progression = self.get_difficulty_progression(student_id)

            # Learning curve
            learning_curve = self.get_learning_curve(student_id)

            # Improvement trend
            improvement_trend = self.get_improvement_trend(student_id)

            # ALS history
            als_history = self.get_als_history(student_id)

            # Streak data
            streak_data = conn.execute("""
                SELECT current_streak, longest_streak FROM student_streaks
                WHERE student_id=?
            """, (student_id,)).fetchone()

            streak_current = streak_data['current_streak'] if streak_data else 0
            streak_longest = streak_data['longest_streak'] if streak_data else 0

            return {
                "overall_accuracy": round(overall_accuracy, 2),
                "total_questions_attempted": total_questions,
                "topic_mastery": topic_mastery,
                "difficulty_progression": difficulty_progression,
                "learning_curve": learning_curve,
                "weak_topics": weak_topics,
                "strong_topics": strong_topics,
                "improvement_trend": improvement_trend,
                "avg_response_time": round(avg_response_time, 2),
                "als_history": als_history,
                "streak_current": streak_current,
                "streak_longest": streak_longest
            }

        except Exception as e:
            print(f"Error getting learning analytics: {e}")
            return {
                "overall_accuracy": 0.0,
                "total_questions_attempted": 0,
                "topic_mastery": [],
                "difficulty_progression": [],
                "learning_curve": [],
                "weak_topics": [],
                "strong_topics": [],
                "improvement_trend": {"improving": False, "change_pct": 0.0},
                "avg_response_time": 0.0,
                "als_history": [],
                "streak_current": 0,
                "streak_longest": 0
            }
        finally:
            conn.close()

    def get_als_history(self, student_id):
        """
        Get ALS score history over time for trend analysis.

        Computes ALS for each unique quiz the student has taken,
        providing a timeline of performance changes.

        Args:
            student_id: The student's unique identifier

        Returns:
            list: ALS scores with dates for charting
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            quizzes = conn.execute("""
                SELECT DISTINCT quiz_id, MIN(created_at) as date
                FROM question_attempts
                WHERE student_id=?
                GROUP BY quiz_id
                ORDER BY MIN(created_at) ASC
            """, (student_id,)).fetchall()

            als_history = []
            for quiz in quizzes:
                als_data = self.calculate_als(student_id, quiz['quiz_id'])
                als_history.append({
                    'date': quiz['date'],
                    'als': als_data['als'],
                    'accuracy': als_data['accuracy_score'],
                    'quiz_id': quiz['quiz_id']
                })

            return als_history

        except Exception as e:
            print(f"Error getting ALS history: {e}")
            return []
        finally:
            conn.close()

    def get_difficulty_progression(self, student_id):
        """
        Track how difficulty levels have changed over time.

        Shows the progression of questions answered at each difficulty
        level, indicating adaptive difficulty adjustments.

        Args:
            student_id: The student's unique identifier

        Returns:
            list: Difficulty progression data with dates
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            progression = conn.execute("""
                SELECT DATE(created_at) as date, difficulty,
                       COUNT(*) as count,
                       SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) as correct
                FROM question_attempts
                WHERE student_id=?
                GROUP BY DATE(created_at), difficulty
                ORDER BY DATE(created_at) ASC
            """, (student_id,)).fetchall()

            return [
                {
                    'date': p['date'],
                    'difficulty': p['difficulty'],
                    'count': p['count'],
                    'correct': p['correct'],
                    'accuracy': (p['correct'] / max(p['count'], 1)) * 100
                }
                for p in progression
            ]

        except Exception as e:
            print(f"Error getting difficulty progression: {e}")
            return []
        finally:
            conn.close()

    def get_learning_curve(self, student_id):
        """
        Get performance over time for charting a learning curve.

        Provides daily accuracy and ALS scores to visualize
        the student's learning trajectory.

        Args:
            student_id: The student's unique identifier

        Returns:
            list: Daily performance data for learning curve chart
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            daily = conn.execute("""
                SELECT DATE(created_at) as date,
                       COUNT(*) as total,
                       SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END) as correct,
                       AVG(response_time) as avg_time
                FROM question_attempts
                WHERE student_id=?
                GROUP BY DATE(created_at)
                ORDER BY DATE(created_at) ASC
            """, (student_id,)).fetchall()

            learning_curve = []
            for day in daily:
                accuracy = (day['correct'] / max(day['total'], 1)) * 100
                # Estimate ALS from daily accuracy
                estimated_als = min(100, accuracy * 1.0)
                learning_curve.append({
                    'date': day['date'],
                    'accuracy': round(accuracy, 2),
                    'als': round(estimated_als, 2),
                    'questions_attempted': day['total'],
                    'avg_response_time': round(day['avg_time'], 2) if day['avg_time'] else 0
                })

            return learning_curve

        except Exception as e:
            print(f"Error getting learning curve: {e}")
            return []
        finally:
            conn.close()

    def get_improvement_trend(self, student_id):
        """
        Calculate improvement metrics by comparing recent vs earlier performance.

        Analyzes whether the student is improving, declining, or stable
        by comparing accuracy and response time across time periods.

        Args:
            student_id: The student's unique identifier

        Returns:
            dict: Improvement status with percentage change
        """
        conn = get_db()
        conn.row_factory = sqlite3.Row

        try:
            # Get total attempts to determine if enough data exists
            total = conn.execute("""
                SELECT COUNT(*) as count FROM question_attempts WHERE student_id=?
            """, (student_id,)).fetchone()

            if not total or total['count'] < 4:
                return {"improving": None, "change_pct": 0.0, "message": "Insufficient data"}

            # Split into two halves for comparison
            all_attempts = conn.execute("""
                SELECT is_correct, response_time FROM question_attempts
                WHERE student_id=?
                ORDER BY created_at ASC
            """, (student_id,)).fetchall()

            mid = len(all_attempts) // 2
            first_half = all_attempts[:mid]
            second_half = all_attempts[mid:]

            # Calculate accuracy for each half
            first_accuracy = (sum(1 for a in first_half if a['is_correct']) / max(len(first_half), 1)) * 100
            second_accuracy = (sum(1 for a in second_half if a['is_correct']) / max(len(second_half), 1)) * 100

            # Calculate average response time for each half
            first_times = [a['response_time'] for a in first_half if a['response_time']]
            second_times = [a['response_time'] for a in second_half if a['response_time']]
            first_avg_time = sum(first_times) / max(len(first_times), 1)
            second_avg_time = sum(second_times) / max(len(second_times), 1)

            # Calculate change percentage
            accuracy_change = second_accuracy - first_accuracy
            time_change = first_avg_time - second_avg_time  # positive = improved (faster)

            # Overall improvement (accuracy improvement + time improvement)
            overall_change = accuracy_change + (time_change * 0.5)
            improving = overall_change > 0

            return {
                "improving": improving,
                "change_pct": round(overall_change, 2),
                "accuracy_change": round(accuracy_change, 2),
                "time_improvement": round(time_change, 2),
                "first_half_accuracy": round(first_accuracy, 2),
                "second_half_accuracy": round(second_accuracy, 2),
                "first_half_avg_time": round(first_avg_time, 2),
                "second_half_avg_time": round(second_avg_time, 2),
                "message": "Improving" if improving else "Needs more practice"
            }

        except Exception as e:
            print(f"Error getting improvement trend: {e}")
            return {"improving": None, "change_pct": 0.0, "message": "Error calculating"}
        finally:
            conn.close()
