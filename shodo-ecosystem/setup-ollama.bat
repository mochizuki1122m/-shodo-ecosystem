@echo off
echo ========================================
echo   Shodo Ecosystem - Ollama Setup
echo   (Windows - Docker-free LLM)
echo ========================================
echo.

REM Check if Ollama is installed
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Ollama is not installed. Opening download page...
    echo.
    echo Please download and install Ollama from:
    echo https://ollama.com/download/windows
    echo.
    start https://ollama.com/download/windows
    echo After installation, run this script again.
    pause
    exit /b 1
)

echo [✓] Ollama is installed
echo.

REM Start Ollama service
echo [1/3] Starting Ollama service...
start "Ollama Service" cmd /c "ollama serve"
timeout /t 3 /nobreak >nul

REM Pull model if not exists
echo [2/3] Checking for Mistral model...
ollama list | findstr "mistral" >nul 2>&1
if %errorlevel% neq 0 (
    echo Downloading Mistral model (this may take a few minutes)...
    ollama pull mistral
) else (
    echo [✓] Mistral model already available
)

REM Test the API
echo.
echo [3/3] Testing Ollama API...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% eq 0 (
    echo [✓] Ollama API is running at http://localhost:11434
) else (
    echo [!] Warning: Could not connect to Ollama API
)

echo.
echo ========================================
echo   Ollama Setup Complete!
echo ========================================
echo.
echo Available models:
ollama list
echo.
echo To use with Shodo:
echo   - API URL: http://localhost:11434/v1
echo   - Model: mistral
echo.
pause