import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

if __name__ == "__main__":
    print("=" * 60)
    print("  AI Personalized Learning System")
    print("  Starting server at http://localhost:5000")
    print("=" * 60)
    print()
    print("  Demo Credentials:")
    print("  Student: student@system.com / student123")
    print("  Mentor:  mentor@system.com / mentor123")
    print("  Admin:   admin@system.com / admin123")
    print()
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
