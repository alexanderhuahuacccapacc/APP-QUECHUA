@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0" || exit /b 1
set "asus2_falta=0"

echo === Codigo ===
where git >nul 2>&1
if errorlevel 1 (
    echo AVISO Git no aparece en PATH.
) else (
    git rev-parse --git-dir >nul 2>&1
    if errorlevel 1 (
        echo AVISO Esta carpeta no es un clon de Git.
    ) else (
        git status --short --branch --untracked-files=no
        git log -1 --oneline
        git symbolic-ref --quiet HEAD >nul 2>&1
        if errorlevel 1 echo AVISO Para usar git pull, selecciona la rama main.
    )
)
call :revisar app\__main__.py
call :revisar asus.py
call :revisar pyproject.toml
call :revisar uv.lock
call :revisar scripts\install_asus2.py

echo.
echo === Modelos ===
call :revisar models\ASUS2\model_index.json
call :revisar models\ASUS2\speech\config.json
call :revisar models\ASUS2\speech\model.safetensors 1933940224
call :revisar models\ASUS2\translation\config.json
call :revisar models\ASUS2\translation\model.safetensors 2460354912
call :revisar models\manifest.json
call :revisar models\whisper-es\model.safetensors 151061672
call :revisar models\tts-quz\model.safetensors 145226744

echo.
echo === Python y bibliotecas ===
set "asus2_python=.venv\Scripts\python.exe"
if exist ".venv-asus2\Scripts\python.exe" set "asus2_python=.venv-asus2\Scripts\python.exe"
if defined UV_PROJECT_ENVIRONMENT set "asus2_python=%UV_PROJECT_ENVIRONMENT%\Scripts\python.exe"
if not exist "%asus2_python%" (
    echo FALTA "%asus2_python%". Ejecuta uv sync --python 3.12 --locked --no-dev.
    set "asus2_falta=1"
    goto resultado
)
echo Entorno "%asus2_python%"
set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
"%asus2_python%" -B -c "import sys; print(sys.version.split()[0]); sys.exit(sys.version_info[:2] != (3, 12))"
if errorlevel 1 (
    echo FALTA Python 3.12 en el entorno seleccionado.
    set "asus2_falta=1"
    goto resultado
)
where uv >nul 2>&1
if errorlevel 1 (
    echo AVISO uv no aparece en PATH.
) else (
    uv pip check --python "%asus2_python%"
    if errorlevel 1 set "asus2_falta=1"
)
"%asus2_python%" -B -c "import app.ui.asus2_desktop, paramiko, scipy, sentencepiece, torch; from transformers import Wav2Vec2ForCTC, WhisperForConditionalGeneration, AutoModelForSeq2SeqLM"
if errorlevel 1 (
    echo FALTA cargar una biblioteca o el codigo de escritorio. Revisa el error anterior.
    set "asus2_falta=1"
) else (
    echo OK carga de bibliotecas
)

:resultado
echo.
if "%asus2_falta%"=="0" (
    echo OK diagnostico de instalacion
) else (
    echo Diagnostico incompleto. Revisa las lineas FALTA o ERROR.
)
exit /b %asus2_falta%

:revisar
if not exist "%~1" (
    echo FALTA %~1
    set "asus2_falta=1"
    exit /b 0
)
for %%F in ("%~1") do (
    if not "%~2"=="" if not "%%~zF"=="%~2" (
        echo ERROR %~1 tiene %%~zF bytes. Se esperaban %~2 bytes.
        set "asus2_falta=1"
        exit /b 0
    )
    echo OK %~1 ^(%%~zF bytes^)
)
exit /b 0
