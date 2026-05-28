@echo off
title Atualizador do Robo de Vagas
echo ====================================================
echo   ATUALIZADOR AUTOMATICO
echo ====================================================
echo.
echo Baixando a versao mais recente do sistema...
curl -L -o atualizacao.zip https://github.com/CaioHCr/Vagas-Automation/archive/refs/heads/master.zip

echo.
echo Extraindo os arquivos...
powershell -command "Expand-Archive -Force atualizacao.zip -DestinationPath temp_update"

echo.
echo Aplicando atualizacao (suas configuracoes serao mantidas)...
xcopy /Y /E /Q "temp_update\Vagas-Automation-master\*" .

echo.
echo Limpando arquivos temporarios...
rmdir /S /Q temp_update
del atualizacao.zip

echo.
echo ====================================================
echo   ATUALIZACAO CONCLUIDA COM SUCESSO!
echo ====================================================
echo.
echo Agora vamos rodar o instalador rapidinho so para 
echo garantir que voce tem todas as dependencias novas...
echo.
pause
call "INSTALE CLICANDO AQUI.bat"
