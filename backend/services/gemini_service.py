import json
import os
import requests
import config

gemini_available = False

OPENROUTER_API_KEY = getattr(config, "OPENROUTER_API_KEY", "") or os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS = [
    "openrouter/free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-4-maverick:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "qwen/qwen3-8b:free",
]
OPENROUTER_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://localhost:5000",
    "X-Title": "AI Learning System",
}
OPENROUTER_MODEL = OPENROUTER_MODELS[0]


def get_model():
    return OPENROUTER_MODEL


def _test_connection():
    global gemini_available, OPENROUTER_MODEL
    print(f"[AI] API Key present: {bool(OPENROUTER_API_KEY)}")
    print(f"[AI] API Key prefix: {OPENROUTER_API_KEY[:15]}..." if OPENROUTER_API_KEY else "[AI] No key")
    if not OPENROUTER_API_KEY:
        print("[AI] No OPENROUTER_API_KEY found - using fallback")
        return
    for model_name in OPENROUTER_MODELS:
        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers=OPENROUTER_HEADERS,
                json={
                    "model": model_name,
                    "messages": [{"role": "user", "content": "Say hi"}],
                    "max_tokens": 10,
                },
                timeout=30,
            )
            print(f"[AI] Testing model {model_name}: {resp.status_code}")
            if resp.status_code == 200:
                OPENROUTER_MODEL = model_name
                gemini_available = True
                print(f"[AI] OpenRouter connected with model: {model_name}")
                return
            else:
                err = resp.text[:200]
                print(f"[AI] Model {model_name} failed: {err}")
        except Exception as e:
            print(f"[AI] Model {model_name} error: {e}")
        break
    print("[AI] No working model found - using fallback")
    print("[AI] No working model found - using fallback")


if not os.getenv("VERCEL"):
    _test_connection()


def is_available():
    return gemini_available


def _call_ai(prompt, temperature=0.3):
    if not gemini_available:
        return None
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers=OPENROUTER_HEADERS,
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": "You are an expert educational content generator. Always respond with valid JSON only, no markdown, no code fences, no extra text."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
                "max_tokens": 4096,
            },
            timeout=120,
        )
        print(f"[AI] API response status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"[AI] Response length: {len(content)} chars")
            return content
        else:
            print(f"[AI] API error {resp.status_code}: {resp.text[:500]}")
            return None
    except Exception as e:
        print(f"[AI] API call error: {e}")
        return None


def _parse_json(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[AI] JSON parse error: {e}")
        print(f"[AI] Raw text (first 500): {text[:500]}")
        return None


def _normalize_question(q):
    text = q.get("question") or q.get("question_text", "")
    opts = q.get("options", ["", "", "", ""])
    if isinstance(opts, list):
        if len(opts) < 4:
            opts = opts + [""] * (4 - len(opts))
    else:
        opts = ["", "", "", ""]

    correct = q.get("correctAnswer") or q.get("correct_answer", "")
    difficulty = q.get("difficulty", "Easy")
    explanation = q.get("explanation", "")

    return {
        "question": text,
        "question_text": text,
        "options": opts,
        "option_a": opts[0],
        "option_b": opts[1],
        "option_c": opts[2],
        "option_d": opts[3],
        "correctAnswer": correct,
        "correct_answer": correct,
        "difficulty": difficulty,
        "explanation": explanation,
    }


# ─── QUIZ GENERATION ─────────────────────────────────────────────────

def generate_quiz(topic, subject="", num_easy=5, num_medium=5, num_hard=5):
    total = num_easy + num_medium + num_hard

    if not gemini_available:
        print("[AI] AI not available, using fallback quiz")
        return _fallback_quiz(topic, total)

    prompt = f"""Generate a quiz about "{topic}" in subject "{subject}".

Distribution:
- {num_easy} Easy questions (basic recall, definitions, terminology)
- {num_medium} Medium questions (application, interpretation, scenarios)
- {num_hard} Hard questions (analysis, evaluation, synthesis)

Each question must have exactly 4 options with ONE clearly correct answer.

Return ONLY a valid JSON array:
[
  {{
    "question": "question text",
    "options": ["option A", "option B", "option C", "option D"],
    "correctAnswer": "exact correct option text",
    "difficulty": "Easy",
    "explanation": "educational explanation"
  }}
]"""

    text = _call_ai(prompt)
    if text:
        questions = _parse_json(text)
        if questions and isinstance(questions, list) and len(questions) > 0:
            print(f"[AI] Generated {len(questions)} questions")
            return [_normalize_question(q) for q in questions]

    print("[AI] Quiz generation failed, using fallback")
    return _fallback_quiz(topic, total)


# ─── RECOMMENDATIONS ─────────────────────────────────────────────────

def generate_recommendation(student_data):
    if not gemini_available:
        return _fallback_recommendation(student_data)

    prompt = f"""Analyze this student data and return a JSON object.

Student Data: {json.dumps(student_data, indent=2)}

Return ONLY this JSON:
{{
  "recommendations": ["rec1", "rec2", "rec3"],
  "improvementAreas": ["area1", "area2"],
  "nextSuggestedDifficulty": "Easy or Medium or Hard",
  "focusTopics": ["topic1", "topic2"],
  "studySuggestions": ["suggestion1", "suggestion2"]
}}"""

    text = _call_ai(prompt, temperature=0.4)
    if text:
        result = _parse_json(text)
        if result:
            return result

    return _fallback_recommendation(student_data)


# ─── PERFORMANCE ANALYSIS ────────────────────────────────────────────

def analyze_performance(student_data):
    if not gemini_available:
        return _fallback_analysis(student_data)

    prompt = f"""Analyze this student performance data.

Data: {json.dumps(student_data, indent=2)}

Return ONLY this JSON:
{{
  "knowledgeGaps": ["gap1", "gap2"],
  "weakConcepts": ["concept1", "concept2"],
  "improvementSuggestions": ["suggestion1", "suggestion2"],
  "learningPattern": "improving/declining/stable",
  "strengths": ["strength1"],
  "estimatedLearningSpeed": "Fast/Medium/Slow",
  "predictedNextScore": 0
}}"""

    text = _call_ai(prompt, temperature=0.3)
    if text:
        result = _parse_json(text)
        if result:
            return result

    return _fallback_analysis(student_data)


# ─── FALLBACK FUNCTIONS ──────────────────────────────────────────────

def _fallback_quiz(topic, total):
    topic_data = {
        "digestive": [
            {"question": "What is the primary function of the digestive system?", "options": ["To pump blood", "To break down food and absorb nutrients", "To produce hormones", "To filter waste from blood"], "correctAnswer": "To break down food and absorb nutrients", "difficulty": "Easy", "explanation": "The digestive system breaks down food into nutrients for absorption."},
            {"question": "Which organ produces bile?", "options": ["Stomach", "Pancreas", "Liver", "Small intestine"], "correctAnswer": "Liver", "difficulty": "Easy", "explanation": "The liver produces bile which helps digest fats."},
            {"question": "Where does most nutrient absorption occur?", "options": ["Large intestine", "Stomach", "Small intestine", "Mouth"], "correctAnswer": "Small intestine", "difficulty": "Medium", "explanation": "The small intestine villi maximize nutrient absorption."},
            {"question": "What is the role of hydrochloric acid in the stomach?", "options": ["Neutralize toxins", "Kill bacteria and activate enzymes", "Absorb vitamins", "Produce mucus"], "correctAnswer": "Kill bacteria and activate enzymes", "difficulty": "Medium", "explanation": "HCl creates acidic pH for pepsin activation and kills pathogens."},
            {"question": "Which enzyme breaks down starch in the mouth?", "options": ["Pepsin", "Amylase", "Lipase", "Trypsin"], "correctAnswer": "Amylase", "difficulty": "Hard", "explanation": "Salivary amylase initiates starch digestion."},
        ],
        "photosynthesis": [
            {"question": "What is photosynthesis?", "options": ["Breaking down glucose", "Converting light to chemical energy", "Protein synthesis", "Cell division"], "correctAnswer": "Converting light to chemical energy", "difficulty": "Easy", "explanation": "Plants convert sunlight into glucose via photosynthesis."},
            {"question": "Which pigment absorbs sunlight?", "options": ["Chlorophyll", "Melanin", "Hemoglobin", "Carotene"], "correctAnswer": "Chlorophyll", "difficulty": "Easy", "explanation": "Chlorophyll absorbs red and blue light for photosynthesis."},
            {"question": "Where does photosynthesis occur?", "options": ["Mitochondria", "Nucleus", "Chloroplast", "Ribosome"], "correctAnswer": "Chloroplast", "difficulty": "Medium", "explanation": "Chloroplasts contain thylakoid membranes where light reactions occur."},
            {"question": "What are the products of the light-dependent reactions?", "options": ["Glucose and oxygen", "ATP and NADPH", "CO2 and water", "Ethanol and ATP"], "correctAnswer": "ATP and NADPH", "difficulty": "Hard", "explanation": "Light reactions produce ATP and NADPH for the Calvin cycle."},
        ],
        "machine learning": [
            {"question": "What is supervised learning?", "options": ["Learning without labels", "Learning with labeled data", "Reinforcement from environment", "Clustering data"], "correctAnswer": "Learning with labeled data", "difficulty": "Easy", "explanation": "Supervised learning uses labeled training data."},
            {"question": "What is overfitting?", "options": ["Model too simple", "Model memorizes training data too well", "Model trains too fast", "Model has too few parameters"], "correctAnswer": "Model memorizes training data too well", "difficulty": "Medium", "explanation": "Overfitting occurs when a model learns noise instead of signal."},
            {"question": "What is the bias-variance tradeoff?", "options": ["Tradeoff between accuracy and speed", "Tradeoff between underfitting and overfitting", "Tradeoff between data size and model size", "Tradeoff between precision and recall"], "correctAnswer": "Tradeoff between underfitting and overfitting", "difficulty": "Hard", "explanation": "High bias = underfitting, high variance = overfitting."},
        ],
        "python": [
            {"question": "What is a list in Python?", "options": ["Immutable sequence", "Mutable ordered collection", "Key-value store", "Set of unique items"], "correctAnswer": "Mutable ordered collection", "difficulty": "Easy", "explanation": "A list is a mutable, ordered sequence of items in Python."},
            {"question": "What does len() do?", "options": ["Returns type", "Returns length", "Converts to string", "Opens file"], "correctAnswer": "Returns length", "difficulty": "Easy", "explanation": "len() returns the number of items in a container."},
            {"question": "What is a dictionary in Python?", "options": ["Ordered list", "Key-value pair collection", "Set of numbers", "Tuple wrapper"], "correctAnswer": "Key-value pair collection", "difficulty": "Medium", "explanation": "A dict stores key-value pairs for fast lookups."},
            {"question": "What is the difference between list and tuple?", "options": ["List is immutable", "Tuple is immutable", "Both are mutable", "Both are immutable"], "correctAnswer": "Tuple is immutable", "difficulty": "Medium", "explanation": "Tuples cannot be modified after creation, lists can."},
            {"question": "What is a decorator in Python?", "options": ["A design pattern", "A function that modifies another function", "A class method", "A variable type"], "correctAnswer": "A function that modifies another function", "difficulty": "Hard", "explanation": "Decorators wrap functions to extend behavior without modifying the original."},
        ],
        "data structure": [
            {"question": "What is a stack?", "options": ["FIFO data structure", "LIFO data structure", "Random access", "Hierarchical structure"], "correctAnswer": "LIFO data structure", "difficulty": "Easy", "explanation": "A stack follows Last-In-First-Out principle."},
            {"question": "What is a queue?", "options": ["FIFO data structure", "LIFO data structure", "Tree structure", "Hash table"], "correctAnswer": "FIFO data structure", "difficulty": "Easy", "explanation": "A queue follows First-In-First-Out principle."},
            {"question": "What is the time complexity of binary search?", "options": ["O(n)", "O(log n)", "O(n^2)", "O(1)"], "correctAnswer": "O(log n)", "difficulty": "Medium", "explanation": "Binary search halves the search space each iteration."},
            {"question": "What is a hash table?", "options": ["Sorted array", "Key-value store with hash function", "Linked list variant", "Binary tree"], "correctAnswer": "Key-value store with hash function", "difficulty": "Medium", "explanation": "Hash tables use a hash function to map keys to indices for O(1) average lookup."},
            {"question": "Explain graph DFS vs BFS", "options": ["DFS uses queue, BFS uses stack", "DFS uses stack, BFS uses queue", "Both use stack", "Both use queue"], "correctAnswer": "DFS uses stack, BFS uses queue", "difficulty": "Hard", "explanation": "DFS uses a stack (recursive), BFS uses a queue for traversal."},
        ],
        "network": [
            {"question": "What does TCP stand for?", "options": ["Transmission Control Protocol", "Transfer Control Protocol", "Transport Communication Protocol", "Terminal Connection Protocol"], "correctAnswer": "Transmission Control Protocol", "difficulty": "Easy", "explanation": "TCP is a reliable, connection-oriented transport protocol."},
            {"question": "What is an IP address?", "options": ["Physical device address", "Unique network identifier", "Domain name", "Protocol version"], "correctAnswer": "Unique network identifier", "difficulty": "Easy", "explanation": "An IP address uniquely identifies a device on a network."},
            {"question": "What is the OSI model layer for TCP?", "options": ["Physical layer", "Transport layer", "Application layer", "Network layer"], "correctAnswer": "Transport layer", "difficulty": "Medium", "explanation": "TCP operates at Layer 4 (Transport) of the OSI model."},
            {"question": "What is DNS?", "options": ["Domain Name System", "Digital Network Service", "Data Network Security", "Distributed Node System"], "correctAnswer": "Domain Name System", "difficulty": "Medium", "explanation": "DNS translates domain names to IP addresses."},
            {"question": "Explain the difference between TCP and UDP", "options": ["TCP is faster", "UDP is connection-oriented", "TCP is reliable, UDP is faster", "Both are identical"], "correctAnswer": "TCP is reliable, UDP is faster", "difficulty": "Hard", "explanation": "TCP ensures delivery with ACKs, UDP is connectionless and faster."},
        ],
        "database": [
            {"question": "What is a primary key?", "options": ["Unique identifier for a row", "Foreign reference", "Index type", "Table name"], "correctAnswer": "Unique identifier for a row", "difficulty": "Easy", "explanation": "A primary key uniquely identifies each row in a table."},
            {"question": "What does SQL stand for?", "options": ["Structured Query Language", "Simple Query Language", "Standard Query Logic", "System Query Language"], "correctAnswer": "Structured Query Language", "difficulty": "Easy", "explanation": "SQL is the standard language for relational database operations."},
            {"question": "What is a JOIN in SQL?", "options": ["Combines rows from tables", "Deletes rows", "Creates table", "Updates data"], "correctAnswer": "Combines rows from tables", "difficulty": "Medium", "explanation": "JOIN combines columns from one or more tables based on related columns."},
            {"question": "What is normalization?", "options": ["Duplicating data", "Organizing data to reduce redundancy", "Encrypting data", "Compressing data"], "correctAnswer": "Organizing data to reduce redundancy", "difficulty": "Medium", "explanation": "Normalization eliminates redundant data and ensures dependencies make sense."},
            {"question": "What is ACID in databases?", "options": ["Atomicity, Consistency, Isolation, Durability", "Access, Control, Input, Data", "Automated, Centralized, Integrated, Distributed", "All, Create, Insert, Delete"], "correctAnswer": "Atomicity, Consistency, Isolation, Durability", "difficulty": "Hard", "explanation": "ACID properties ensure reliable processing of database transactions."},
        ],
        "algorithm": [
            {"question": "What is Big O notation?", "options": ["Measure of performance", "Code complexity measure", "Algorithm speed scaling", "Memory usage"], "correctAnswer": "Algorithm speed scaling", "difficulty": "Easy", "explanation": "Big O describes how runtime grows with input size."},
            {"question": "What is recursion?", "options": ["Function calling itself", "Loop iteration", "Array method", "Error handling"], "correctAnswer": "Function calling itself", "difficulty": "Easy", "explanation": "Recursion solves problems by calling the same function within itself."},
            {"question": "What is a greedy algorithm?", "options": ["Always picks the best local choice", "Explores all possibilities", "Random selection", "Divides problem into halves"], "correctAnswer": "Always picks the best local choice", "difficulty": "Medium", "explanation": "Greedy algorithms make the locally optimal choice at each step."},
            {"question": "Explain dynamic programming", "options": ["Solving subproblems once and reusing", "Dynamic memory allocation", "Runtime code generation", "Parallel computing"], "correctAnswer": "Solving subproblems once and reusing", "difficulty": "Medium", "explanation": "DP breaks problems into overlapping subproblems and stores results."},
            {"question": "What is the time complexity of quicksort?", "options": ["O(n) average", "O(n log n) average", "O(n^2) average", "O(log n) average"], "correctAnswer": "O(n log n) average", "difficulty": "Hard", "explanation": "Quicksort averages O(n log n) with O(n^2) worst case."},
        ],
    }

    key = topic.lower()
    for k, questions in topic_data.items():
        if k in key:
            qs = questions
            while len(qs) < total:
                qs.extend(questions)
            return [_normalize_question(q) for q in qs[:total]]

    generic_templates = [
        {"question": f"What is the basic definition of {topic}?", "options": [f"{topic} refers to A", f"{topic} refers to B", f"{topic} refers to C", f"{topic} refers to D"], "correctAnswer": f"{topic} refers to A", "difficulty": "Easy", "explanation": f"Definition: {topic} is best described by option A."},
        {"question": f"Which is a key characteristic of {topic}?", "options": [f"Characteristic X of {topic}", f"Characteristic Y of {topic}", f"Characteristic Z of {topic}", f"Characteristic W of {topic}"], "correctAnswer": f"Characteristic X of {topic}", "difficulty": "Easy", "explanation": f"Characteristic X is a defining feature of {topic}."},
        {"question": f"In what context is {topic} commonly applied?", "options": ["Context A", "Context B", "Context C", "Context D"], "correctAnswer": "Context B", "difficulty": "Medium", "explanation": f"{topic} is commonly applied in context B."},
        {"question": f"How does {topic} differ from related concepts?", "options": ["Difference A", "Difference B", "Difference C", "Difference D"], "correctAnswer": "Difference A", "difficulty": "Medium", "explanation": f"The key distinction of {topic} is difference A."},
        {"question": f"What is a real-world example of {topic}?", "options": [f"Example 1 of {topic}", f"Example 2 of {topic}", f"Example 3 of {topic}", f"Example 4 of {topic}"], "correctAnswer": f"Example 1 of {topic}", "difficulty": "Medium", "explanation": f"A practical application of {topic}."},
        {"question": f"Evaluate: '{topic} is always applicable'.", "options": ["True", "False - depends on context", "Partially true", "Not enough info"], "correctAnswer": "False - depends on context", "difficulty": "Hard", "explanation": f"The applicability of {topic} varies."},
        {"question": f"What is the main limitation of {topic}?", "options": ["Limitation A", "Limitation B", "Limitation C", "Limitation D"], "correctAnswer": "Limitation B", "difficulty": "Hard", "explanation": f"The main constraint of {topic} involves factor B."},
        {"question": f"Compare {topic} with alternatives.", "options": [f"{topic} is better", "Alternative is better", "Both equal", "Depends on use case"], "correctAnswer": "Depends on use case", "difficulty": "Hard", "explanation": "The best choice depends on requirements."},
    ]
    result = [_normalize_question(q) for q in generic_templates]
    while len(result) < total:
        result.append(result[-1])
    return result[:total]


def _fallback_recommendation(student_data):
    weak = []
    topic_data = student_data.get("topicAnalysis", [])
    for t in topic_data:
        acc = t.get("accuracy", 0)
        if acc < 60:
            weak.append(t.get("topic", "Unknown"))
    avg = sum(t.get("accuracy", 0) for t in topic_data) / len(topic_data) if topic_data else 50
    next_diff = "Easy" if avg < 60 else "Medium" if avg < 75 else "Hard"
    return {
        "recommendations": [f"Focus on improving {', '.join(weak) if weak else 'all topics'}.", "Practice with more quizzes.", "Review fundamental concepts."],
        "improvementAreas": weak if weak else ["General knowledge building"],
        "nextSuggestedDifficulty": next_diff,
        "focusTopics": weak if weak else ["Current topics"],
        "studySuggestions": ["Create a study schedule", "Use flashcards for key concepts", "Take practice quizzes regularly"],
    }


def _fallback_analysis(student_data):
    results = student_data.get("recentResults", [])
    topic_data = student_data.get("topicAnalysis", [])
    total = len(results)
    if total == 0:
        return {"knowledgeGaps": ["Insufficient data"], "weakConcepts": ["Complete more quizzes"], "improvementSuggestions": ["Start taking quizzes"], "learningPattern": "insufficient_data", "strengths": [], "estimatedLearningSpeed": "Medium", "predictedNextScore": 50}
    accuracies = [r.get("accuracy", 0) for r in results]
    avg_acc = sum(accuracies) / len(accuracies) if accuracies else 0
    trend = "stable"
    if total >= 2:
        recent = accuracies[:min(3, total)]
        older = accuracies[-min(3, total):]
        if sum(recent) / len(recent) > sum(older) / len(older):
            trend = "improving"
        elif sum(recent) / len(recent) < sum(older) / len(older):
            trend = "declining"
    speed = "Slow" if avg_acc < 40 else "Medium" if avg_acc < 70 else "Fast"
    gaps = [t.get("topic", "Unknown") for t in topic_data if t.get("avg_accuracy", 100) < 60]
    strengths = [t.get("topic", "Unknown") for t in topic_data if t.get("avg_accuracy", 0) >= 80]
    return {"knowledgeGaps": gaps or ["Complete more quizzes"], "weakConcepts": gaps or ["N/A"], "improvementSuggestions": ["Review weak topics", "Focus on core concepts", "Practice regularly"], "learningPattern": trend, "strengths": strengths or ["Keep building"], "estimatedLearningSpeed": speed, "predictedNextScore": round(avg_acc + 5, 2) if trend == "improving" else round(avg_acc - 3, 2) if trend == "declining" else round(avg_acc, 2)}
