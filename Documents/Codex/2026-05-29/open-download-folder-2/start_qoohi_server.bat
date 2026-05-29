@echo off
title QOOHI Server
cd /d "%~dp0"
echo Starting QOOHI server...
echo.
echo Admin page: http://127.0.0.1:8080/admin
echo Default PIN: 1234
echo.
python app.py
if %errorlevel% neq 0 (
    echo.
    echo Python not found. Trying "py" instead...
    py app.py
)
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Python is not installed or not in PATH.
    echo Install Python 3 from https://www.python.org/downloads/windows/
    echo During install, tick "Add python.exe to PATH".
    pause
)
