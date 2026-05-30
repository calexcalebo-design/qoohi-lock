@echo off
echo QOOHI customer agent - PC 2
echo.

set SERVER_URL=https://qoohi-lock.onrender.com
set PC_ID=2
set PC_TOKEN=98lqBSvXdbhq-ZHQ3jW9Pg

echo Server: %SERVER_URL%
echo PC ID:   %PC_ID%
echo.

:loop
where py >nul 2>nul
if %errorlevel%==0 (
  py customer_agent.py "%SERVER_URL%" "%PC_ID%" "%PC_TOKEN%"
  goto restart_msg
)

where python >nul 2>nul
if %errorlevel%==0 (
  python customer_agent.py "%SERVER_URL%" "%PC_ID%" "%PC_TOKEN%"
  goto restart_msg
)

echo Python is not installed on this PC.
echo Install Python 3 from https://www.python.org/downloads/windows/
echo During install, tick "Add python.exe to PATH".
pause
exit /b

:restart_msg
echo Agent was closed. Restarting in 1 second...
timeout /t 1 >nul
goto loop