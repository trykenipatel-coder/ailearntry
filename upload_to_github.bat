@echo off
echo Removing old git history to clear secrets...
rmdir /s /q .git

echo Initializing fresh git repository...
git init
git add .

echo Committing changes...
git commit -m "Upload all code and folders"

echo Setting remote URL...
git remote add origin https://github.com/trykenipatel-coder/ailearntry.git

echo Pushing to main branch...
git push -u origin main --force
if errorlevel 1 (
    echo Push to main failed, trying master branch instead...
    git push -u origin master --force
)

echo.
echo Upload complete! Press any key to exit.
pause
