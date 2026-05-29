@echo off
echo QOOHI customer agent
echo.
set /p CUSTOM_URL=Enter Server URL (e.g., https://qoohi-lock.onrender.com): 
if "%CUSTOM_URL%"=="" (
  set SERVER_URL=http://127.0.0.1:8080
) else (
  set SERVER_URL=%CUSTOM_URL%
)
echo Server: %SERVER_URL%
echo.
set /p PC_ID=Enter this customer PC number from QOOHI admin, for example 1 or 2: 
set /p PC_TOKEN=Paste the PC Token from the Admin dashboard: 

where py >nul 2>nul
if %errorlevel%==0 (
  py customer_agent.py "%SERVER_URL%" "%PC_ID%" "%PC_TOKEN%"
  exit /b
)

where python >nul 2>nul
if %errorlevel%==0 (
  python customer_agent.py "%SERVER_URL%" "%PC_ID%" "%PC_TOKEN%"
  exit /b
)

echo Python is not installed on this PC.
echo Install Python 3 from https://www.python.org/downloads/windows/
echo During install, tick "Add python.exe to PATH".
pause
