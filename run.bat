@echo off
rem بدون pause — این فایل زیر Task Scheduler در سشن غیرتعاملی (SYSTEM) اجرا می‌شود
rem و pause باعث می‌شد cmd تا بی‌نهایت معلق بماند.
cd /d "%~dp0"
python droperog.py >> "data\run_log.txt" 2>&1
exit /b %errorlevel%
