@echo off
echo Starting Redis, Celery, and Django...
cd /d %~dp0..

:: Kill any existing celery workers
taskkill /f /im celery.exe 2>nul

:: Start celery in background
start "Celery Worker" cmd /k "celery -A cookieguard worker -l info --pool=solo"

:: Wait a sec for celery to start
timeout /t 2 /nobreak >nul

:: Start Django
python manage.py runserver
