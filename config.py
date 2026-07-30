import os
from dotenv import load_dotenv

# Explicitly load .env from the project root
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "your-secret-key-here")
DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
if os.getenv("VERCEL"):
    DATABASE_PATH = "/tmp/learning_system.db"
else:
    DATABASE_PATH = os.path.join(BASE_DIR, "learning_system.db")

# Firebase Admin SDK
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
FIREBASE_PRIVATE_KEY = os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n")
FIREBASE_CLIENT_EMAIL = os.getenv("FIREBASE_CLIENT_EMAIL", "")
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "")
FIREBASE_STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "")

# Firebase Web SDK (frontend)
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY", "")
FIREBASE_AUTH_DOMAIN = os.getenv("FIREBASE_AUTH_DOMAIN", "")
FIREBASE_PROJECT_ID_WEB = os.getenv("FIREBASE_PROJECT_ID_WEB", "")

# Gemini / OpenRouter
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Quiz settings
MAX_VIOLATIONS = 2
QUIZ_TIME_MINUTES = 15
