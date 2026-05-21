@echo off
:: Auto-unblock (remove Mark of the Web)
powershell -NoProfile -Command "Unblock-File -Path '%~f0'" >nul 2>&1

if "%1"=="" (
    title VAGAS - AGENDADOR
    cmd /k "%~f0" _inner_
    exit
)

cd /d "%~dp0"

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo [ERRO] Ambiente virtual nao encontrado.
    echo Execute INSTALE CLICANDO AQUI.bat primeiro.
    pause
    exit /b 1
)

echo.
echo Iniciando agendador automatico...
echo O pipeline rodara nos horarios configurados.
echo Deixe esta janela aberta em segundo plano.
echo.
python scheduler.py
pause