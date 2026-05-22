@echo off
:: Auto-unblock (remove Mark of the Web)
powershell -NoProfile -Command "Unblock-File -Path '%~f0'" >nul 2>&1

if "%1"=="" (
    title VAGAS - PAINEL
    cmd /k "%~f0" _inner_
    exit
)

cd /d "%~dp0"
if errorlevel 1 (
    echo [ERRO] Nao foi possivel acessar o diretorio.
    pause
    exit /b 1
)
title Vagas Automation - Painel

copy nul "__perm_test.tmp" >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Sem permissao nesta pasta.
    echo        Execute run.bat como Administrador.
    pause
    exit /b 1
)
del "__perm_test.tmp" >nul 2>&1

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    where conda >nul 2>&1
    if not errorlevel 1 (
        call conda activate base
    ) else (
        echo [ERRO] Ambiente virtual nao encontrado.
        echo Execute "INSTALE CLICANDO AQUI.bat" primeiro.
        pause
        exit /b 1
    )
)

python -m streamlit run app.py
if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel iniciar o painel.
    pause
)
