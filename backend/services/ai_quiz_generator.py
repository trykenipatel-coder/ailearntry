import json
import requests
from config import GEMINI_API_KEY

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def generate_quiz(topic, subject="", num_questions=5):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        return None

    prompt = f"""Generate {num_questions} multiple choice questions about "{topic}" in the subject "{subject}".

For each question, provide:
- question_text: The question
- option_a, option_b, option_c, option_d: Four answer options
- correct_answer: The correct option letter (A, B, C, or D)
- difficulty: Easy, Medium, or Hard
- explanation: Brief explanation of the correct answer

Return ONLY a valid JSON array of objects. Example format:
[
  {{
    "question_text": "What is ...?",
    "option_a": "Answer 1",
    "option_b": "Answer 2",
    "option_c": "Answer 3",
    "option_d": "Answer 4",
    "correct_answer": "A",
    "difficulty": "Easy",
    "explanation": "Explanation here"
  }}
]"""

    try:
        response = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 2048,
                },
            },
            timeout=30,
        )

        if response.status_code != 200:
            return None

        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]

        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        questions = json.loads(text)
        if isinstance(questions, list) and len(questions) > 0:
            return questions

    except Exception:
        return None

    return None
