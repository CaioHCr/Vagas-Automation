@echo off
cd /d "%~dp0"

echo ===============================================
echo   TESTE DE VALIDACAO PRE-VM
echo ===============================================
echo.

:: 1. Verificar se .env existe e tem todos os campos
echo [1/5] Verificando .env...
if not exist .env (
    echo [FALHA] .env nao encontrado. Copie .env.example ou rode setup.bat.
    exit /b 1
)
findstr /B "OPENAI_API_KEY=" .env >nul || ( echo [FALHA] OPENAI_API_KEY ausente & exit /b 1 )
findstr /B "EMAIL_USUARIO=" .env >nul || ( echo [AVISO] EMAIL_USUARIO ausente - email nao funcionara )
findstr /B "EMAIL_SENHA_APP=" .env >nul || ( echo [AVISO] EMAIL_SENHA_APP ausente - email nao funcionara )
echo [OK] .env valido.

:: 2. Verificar Python e venv
echo [2/5] Verificando Python...
python --version >nul 2>&1 || ( echo [FALHA] Python nao encontrado & exit /b 1 )
for /f "tokens=*" %%i in ('python --version') do echo       %%i

if exist venv\Scripts\python.exe (
    echo [OK] venv existe.
) else (
    echo [FALHA] venv nao encontrado. Rode setup.bat primeiro.
    exit /b 1
)

:: 3. Verificar dependencias instaladas
echo [3/5] Verificando dependencias...
call venv\Scripts\activate.bat
python -c "import streamlit, pandas, requests, openai, dotenv, bs4, schedule, pydantic, pydantic_settings; print('[OK] Todas as', len(['streamlit', 'pandas', 'requests', 'openai', 'dotenv', 'bs4', 'schedule', 'pydantic', 'pydantic_settings']), 'bibliotecas disponiveis.')" 2>&1
if errorlevel 1 (
    echo [FALHA] Biblioteca faltando. Rode setup.bat.
    exit /b 1
)

:: 4. Playwright
echo [4/5] Verificando Playwright...
python -c "from playwright.sync_api import sync_playwright; print('[OK] Playwright disponivel.')" 2>&1
if errorlevel 1 (
    echo [AVISO] Playwright nao funcional. Scrapers usam requests+BS4, entao nao e critico.
)

:: 5. Sintaxe dos modulos
echo [5/5] Verificando sintaxe dos modulos...
cd /d "%~dp0"
python scripts\check_vm.py
if errorlevel 1 (
    echo [FALHA] Erro de sintaxe detectado.
    exit /b 1
)

:: Done
echo.
echo ===============================================
echo   VALIDACAO CONCLUIDA - PRONTO PARA AS VMS
echo ===============================================
echo.
echo   Copie a pasta completa para a VM e rode:
echo     setup.bat
echo     run.bat
echo.
pause
