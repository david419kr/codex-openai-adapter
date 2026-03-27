@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

set "PYTHON_VERSION=3.13"
if exist ".python-version" (
    set /p PYTHON_VERSION=<.python-version
)

call :ensure_uv || exit /b 1

echo Installing codex-openai-adapter
echo Working directory: %CD%
echo Using uv: %UV_EXE%
echo Python version: %PYTHON_VERSION%
echo.

"%UV_EXE%" python install %PYTHON_VERSION% || exit /b 1
if exist ".venv\Scripts\python.exe" (
    echo Reusing existing .venv
) else (
    if exist ".venv\" (
        echo Existing .venv is incompatible with this platform. Recreating...
        powershell -NoProfile -Command "$repo = (Get-Location).Path; $target = Join-Path $repo '.venv'; if (Test-Path -LiteralPath $target) { $parent = (Resolve-Path -LiteralPath (Split-Path -Parent $target)).Path; if ($parent -ne $repo) { throw 'Refusing to remove unexpected path.' }; Remove-Item -LiteralPath $target -Recurse -Force }"
        if errorlevel 1 exit /b 1
        "%UV_EXE%" venv --python %PYTHON_VERSION% .venv || exit /b 1
    ) else (
        "%UV_EXE%" venv --python %PYTHON_VERSION% .venv || exit /b 1
    )
)

if exist "uv.lock" (
    echo Syncing dependencies from uv.lock with dev extras...
    "%UV_EXE%" sync --frozen --extra dev
    if errorlevel 1 (
        echo Frozen sync failed. Retrying with a normal sync...
        "%UV_EXE%" sync --extra dev || exit /b 1
    )
) else (
    echo Syncing dependencies from pyproject.toml with dev extras...
    "%UV_EXE%" sync --extra dev || exit /b 1
)

echo.
echo Installation complete.
echo Start the adapter with:
echo   run-adapter.bat
exit /b 0

:ensure_uv
set "UV_EXE="
for /f "delims=" %%I in ('where uv 2^>nul') do (
    if not defined UV_EXE set "UV_EXE=%%I"
)
if defined UV_EXE exit /b 0

echo uv not found. Installing via the official installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
if errorlevel 1 (
    echo [ERROR] Failed to install uv.
    exit /b 1
)

for %%P in ("%USERPROFILE%\.local\bin\uv.exe" "%USERPROFILE%\.cargo\bin\uv.exe") do (
    if exist %%~fP (
        set "UV_EXE=%%~fP"
    )
)

if not defined UV_EXE (
    for /f "delims=" %%I in ('where uv 2^>nul') do (
        if not defined UV_EXE set "UV_EXE=%%I"
    )
)

if not defined UV_EXE (
    echo [ERROR] uv was installed but could not be located in this shell.
    echo Add uv to PATH or open a new terminal, then rerun install-adapter.bat.
    exit /b 1
)

exit /b 0
