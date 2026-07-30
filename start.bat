@echo off
title AI Personalized Learning System
echo ============================================
echo  AI Personalized Learning System
echo  with Firebase + Gemini Integration
echo ============================================
echo.

if not exist .env (
    echo [INFO] .env not found. Copying from .env.example...
    copy .env.example .env
    echo [WARN] Edit .env with your Firebase and Gemini credentials!
    echo.
)

echo [1/3] Installing dependencies...
pip install -r requirements.txt
echo.

echo [2/3] Starting server...
echo.
echo  Open http://localhost:5000 in your browser
echo.
echo  Demo Accounts (SQLite):
echo  Student: student@system.com / student123
echo  Mentor:  mentor@system.com / mentor123
echo  Admin:   admin@system.com / admin123
echo.
echo  Firebase: Configure .env and firebase_config.js first
echo.
echo ============================================
python run.py
pause
