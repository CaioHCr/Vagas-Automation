@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 (
    echo [ERRO] Nao foi possivel acessar o diretorio do script.
    echo        Caminho: "%~dp0"
    echo        Tente mover a pasta para C:\Users\SeuNome\
    pause
    exit /b 1
)

title Vagas Automation Setup
set PYTHON_VERSION=3.12.9

:: --------------------------------------------------
:: [0/6] Permission check (protected path like C:\)
:: --------------------------------------------------
echo ====================================================
echo   VAGAS AUTOMATION - SETUP
echo ====================================================
echo.
echo [0/6] Verificando permissoes de escrita...
echo Teste: %CD%
copy nul "__perm_test.tmp" >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Sem permissao de escrita em: %CD%
    echo.
    echo        Causas possiveis:
    echo        1. Voce esta em C:\ ou outra pasta protegida
    echo        2. Antivirus bloqueando criacao de arquivo
    echo        3. Disco cheio ou sem espaco
    echo.
    echo        Solucoes:
    echo        - Clique com botao direito ^> "Executar como administrador"
    echo        - Ou mova a pasta para C:\Users\SeuNome\
    echo.
    pause
    exit /b 1
)
del "__perm_test.tmp" >nul 2>&1
echo [OK] Permissao de escrita confirmada.
echo.

:: --------------------------------------------------
:: [1/6] Python detection + auto-install
:: --------------------------------------------------
echo [1/6] Verificando Python...

python --version >nul 2>&1
if not errorlevel 1 goto :python_ok

:: --- Python nao encontrado. Tentar instalar ---
echo [AVISO] Python nao encontrado. Iniciando instalacao automatica...

:: 1a tentativa: winget (Windows 10 1809+)
where winget >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Baixando Python %PYTHON_VERSION% via winget...
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements >nul 2>&1
    if not errorlevel 1 (
        echo [OK] Python instalado via winget.
        goto :refresh_path_python
    )
)

:: 2a tentativa: download direto com curl
where curl >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Nem curl nem winget estao disponiveis neste sistema.
    echo        Instale Python %PYTHON_VERSION% manualmente em https://python.org
    pause
    exit /b 1
)

:: Detectar arquitetura
set ARCH=amd64
if "%PROCESSOR_ARCHITECTURE%"=="x86" set ARCH=win32
set INSTALLER_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-%ARCH%.exe
set INSTALLER_PATH=%TEMP%\python-%PYTHON_VERSION%-%ARCH%.exe

echo [INFO] Baixando Python %PYTHON_VERSION% (%ARCH%)...
echo URL: %INSTALLER_URL%
curl -# -o "%INSTALLER_PATH%" "%INSTALLER_URL%"
if errorlevel 1 (
    echo [ERRO] Falha ao baixar Python. Verifique sua conexao com internet.
    pause
    exit /b 1
)

echo [INFO] Instalando Python (janela pode aparecer e fechar rapidamente)...
"%INSTALLER_PATH%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0 Include_dev=1
if errorlevel 1 (
    echo [ERRO] Falha ao instalar Python.
    pause
    exit /b 1
)
echo [OK] Python %PYTHON_VERSION% instalado.

:refresh_path_python
:: Forcar recarga do PATH para enxergar o Python novo
for /f "tokens=*" %%i in ('%SYSTEMROOT%\System32\reg.exe query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul ^| findstr /i "REG_"') do (
    setx PATH "%%i" >nul
)
:: Refresh local PATH
call "%SYSTEMROOT%\System32\reg.exe" add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /f /v PATH /t REG_SZ /d "" >nul 2>&1
:: Tentar no PATH local
set "PATH=%PATH%;C:\Program Files\Python312\;C:\Program Files\Python312\Scripts\;C:\Program Files\Python312\Tools\scripts\"
:: Verificar
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python instalado mas nao encontrado no PATH.
    echo        Abra um novo terminal e execute setup.bat novamente.
    pause
    exit /b 1
)

:python_ok
echo [OK] Python detectado.
for /f "tokens=*" %%i in ('python --version') do echo       %%i
echo.

:: --------------------------------------------------
:: [2/6] Virtual environment
:: --------------------------------------------------
echo [2/6] Verificando ambiente virtual...

where conda >nul 2>&1
if not errorlevel 1 (
    call conda activate base
    echo [OK] Usando conda base. Pule venv.
    goto :install_deps
)

if exist venv\Scripts\activate.bat (
    echo [OK] venv ja existe.
) else (
    echo [INFO] Criando venv...
    python -m venv venv
    if errorlevel 1 (
        echo [ERRO] Falha ao criar venv.
        pause
        exit /b 1
    )
    echo [OK] venv criada.
)
echo.

:: --------------------------------------------------
:: [3/6] Install dependencies
:: --------------------------------------------------
:install_deps
echo [3/6] Instalando dependencias...

if exist venv\Scripts\activate.bat call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERRO] Falha ao instalar dependencias. Verifique requirements.txt.
    pause
    exit /b 1
)
echo [OK] Dependencias instaladas.
echo.

:: --------------------------------------------------
:: [4/6] Playwright browser
:: --------------------------------------------------
echo [4/6] Verificando Playwright...
python -c "from playwright.sync_api import sync_playwright; sync_playwright().__enter__().browsers.launch()" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando Chromium para Playwright...
    python -m playwright install chromium
    if errorlevel 1 (
        echo [AVISO] Falha ao instalar Chromium. Scraper Gupy pode falhar.
    ) else (
        echo [OK] Chromium instalado.
    )
) else (
    echo [OK] Playwright ja funcional.
)
echo.

:: --------------------------------------------------
:: [5/6] Create config files if missing
:: --------------------------------------------------
echo [5/6] Verificando arquivos de configuracao...

if not exist config\termos_busca.json (
    echo [INFO] Criando config/termos_busca.json com valores padrao...
    if not exist config mkdir config
    echo {"localizacoes_ids": ["106057199", "104514572"], "consultorias_ids": [], "localizacoes_disponiveis": {"Brasil": "106057199", "LATAM": "104514572", "Remoto (Worldwide)": "WORLDWIDE"}} > config\termos_busca.json
)

if not exist .env (
    echo [INFO] Criando arquivo .env com valores padrao...
    (
        echo.# OpenAI
        echo.OPENAI_API_KEY=sk-sua-chave-aqui
        echo.
        echo.# Busca
        echo.CARGOS_ALVO=COO,Diretor de Operacoes,Diretor Industrial
        echo.KEYWORDS_EXECUTIVAS=Turnaround,Excelencia Operacional,Supply Chain
        echo.LOCALIZACAO_FILTRO=Brasil
        echo.
        echo.# Email (Gmail SMTP)
        echo.EMAIL_USUARIO=seu-email@gmail.com
        echo.EMAIL_SENHA_APP=aaaa bbbb cccc dddd
    ) > .env
    echo [AVISO] Edite o arquivo .env com sua chave OpenAI antes de rodar o painel.
)

echo [OK] Arquivos de configuracao prontos.
echo.

:: --------------------------------------------------
:: [6/6] Health check
:: --------------------------------------------------
echo [6/6] Verificando importacoes criticas...
python -c "import streamlit, pandas, requests, openai, dotenv, bs4, schedule, pydantic, pydantic_settings" >nul 2>&1
if errorlevel 1 (
    echo [ERRO] Uma ou mais bibliotecas nao foram instaladas corretamente.
    pause
    exit /b 1
)
echo [OK] Todas as bibliotecas estao disponiveis.
echo.

:: --------------------------------------------------
:: Done
:: --------------------------------------------------
echo ====================================================
echo   SETUP CONCLUIDO COM SUCESSO
echo ====================================================
echo.
echo   Para rodar o painel:
echo     python -m streamlit run app.py
echo.
echo   Ou clique duas vezes em run.bat
echo.
echo   Pressione qualquer tecla para sair...
pause
