@echo off
REM Agent Memory Proxy - Installation Script for Windows

echo ===================================
echo Agent Memory Proxy Installation
echo ===================================

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python detected
echo.

REM Install dependencies
echo Installing dependencies...

REM Check if Poetry is installed
where poetry >nul 2>&1
if %errorlevel% equ 0 (
    echo Poetry detected, using Poetry to install...
    poetry install
) else (
    echo Poetry not found, using pip...
    python -m pip install .
)

if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Dependencies installed successfully
echo.

REM Create config directory
if not exist "%APPDATA%\agent-memory-proxy" (
    mkdir "%APPDATA%\agent-memory-proxy"
)

REM Create start script
echo Creating start script...
(
echo @echo off
echo cd /d "%CD%"
echo set AGENT_MEMORY_PATHS=%USERPROFILE%\projects
echo python src/main.py
) > start_agent_memory_proxy.bat

echo.
echo ===================================
echo Installation complete!
echo ===================================
echo.
echo Next steps:
echo 1. Set AGENT_MEMORY_PATHS environment variable
echo    - Open System Properties -^> Environment Variables
echo    - Add: AGENT_MEMORY_PATHS = C:\your\project\paths
echo.
echo 2. Create .amp.yaml in your projects
echo.
echo 3. Run the proxy:
echo    - Double-click start_agent_memory_proxy.bat
echo    - Or run: python src/main.py
echo.
echo Optional: Add to Windows startup
echo    - Press Win+R, type: shell:startup
echo    - Copy start_agent_memory_proxy.bat to the folder
echo.
echo See README.md for detailed instructions
echo.
pause
