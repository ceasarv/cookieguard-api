@echo off
cd /d %~dp0..
taskkill /f /im celery.exe 2>nul
celery -A cookieguard worker -l info --pool=solo
