@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

if not "%~1"=="" set "PORT=%~1"
if not "%~2"=="" set "CODEX_AUTH_PATH=%~2"

if not exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    echo [ERROR] .venv not found. Run install-adapter.bat first.
    exit /b 1
)

echo Starting codex-openai-adapter
echo Working directory: %CD%
echo Config sources: CLI args ^> environment variables ^> .env ^> built-in defaults
echo.

"%SCRIPT_DIR%.venv\Scripts\python.exe" -m codex_openai_adapter

endlocal
