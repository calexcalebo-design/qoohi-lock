@echo off
set SERVER_URL=http://192.168.0.114:8080
echo QOOHI customer agent
echo Server: %SERVER_URL%
echo.
set /p PC_ID=Enter this customer PC number from QOOHI admin, for example 1 or 2: 

where py >nul 2>nul
if %errorlevel%==0 (
  py customer_agent.py %SERVER_URL% %PC_ID%
  exit /b
)

where python >nul 2>nul
if %errorlevel%==0 (
  python customer_agent.py %SERVER_URL% %PC_ID%
  exit /b
)

echo Python is not installed on this PC.
echo Install Python 3 from https://www.python.org/downloads/windows/
echo During install, tick "Add python.exe to PATH".
pause
