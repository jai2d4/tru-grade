@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (
  echo Python 3.11 or newer is required.
  exit /b 1
)

if not exist ".tmp" mkdir ".tmp"
set "TEMP=%CD%\.tmp"
set "TMP=%CD%\.tmp"

if not exist ".venv\Scripts\python.exe" python -m venv .venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip

echo.
echo === Web service and test dependencies ===
python -m pip install -r requirements-dev.txt

rem --- PyTorch -------------------------------------------------------------
rem Installed separately, and FIRST, because the wheel index decides whether
rem this is the CUDA build (gigabytes of NVIDIA libraries, needed for GPU
rem analysis) or the CPU build (far smaller, correct on a machine with no
rem NVIDIA GPU). Installing it here means the worker requirements below find
rem torch already satisfied instead of re-resolving to the CUDA default.
rem
rem Override the auto-detection with e.g.:
rem   set TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124
rem Run scripts\check_env.py to see which CUDA version your driver supports.
if "%TORCH_INDEX_URL%"=="" (
  where nvidia-smi >nul 2>nul && (
    set "TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121"
    echo.
    echo === NVIDIA GPU detected - installing CUDA build of PyTorch ===
    echo     If analysis later reports CUDA unavailable, re-run with
    echo     TORCH_INDEX_URL set to match your driver ^(see check_env.py^).
  ) || (
    set "TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu"
    echo.
    echo === No NVIDIA GPU detected - installing CPU build of PyTorch ===
    echo     Analysis will still run, just slower.
  )
)
python -m pip install torch --index-url %TORCH_INDEX_URL%

echo.
echo === Analysis worker dependencies ^(vision stack^) ===
python -m pip install -r requirements-worker.txt

if not exist ".env" copy ".env.example" ".env" >nul

rem Ask for the two values that can't be derived, and write .env directly —
rem hand-editing a config file is the step most likely to go wrong.
echo.
python "%~dp0scripts\configure.py"

echo.
echo === Applying database schema ===
python "%~dp0scripts\init_db.py"

echo.
echo ========================================================
echo Setup complete. Start the app with:
echo.
echo     run_trugrade.bat
echo.
echo ========================================================
endlocal
