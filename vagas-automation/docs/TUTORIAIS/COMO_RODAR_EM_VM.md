# COMO RODAR EM VM WINDOWS PURA

Guia passo a passo para maquinas Windows sem Python, sem nada.

## Requisitos

- Windows 10+ (qualquer edicao)
- Conexao com internet
- 2 GB de espaco em disco

## Instalacao

```cmd
git clone https://github.com/CaioHCr/Vagas-Automation.git
cd Vagas-Automation\vagas-automation
INSTALE CLICANDO AQUI.bat
```

O `INSTALE CLICANDO AQUI.bat` faz tudo automaticamente:

| Passo | O que faz |
|---|---|
| 0 | Testa permissao de escrita |
| 1 | Detecta Python. Se nao existir, instala via winget ou curl direto do python.org |
| 2 | Cria ambiente virtual (venv) |
| 3 | Instala todas as dependencias (`pip install -r requirements.txt`) |
| 4 | Instala Chromium para Playwright (opcional, nao critico) |
| 5 | Cria `config/termos_busca.json` e `.env` com valores padrao |
| 6 | Valida que todas as bibliotecas importam corretamente |

## Pos-instalacao

Antes de rodar, edite o `.env` com sua chave OpenAI:

```cmd
notepad .env
```

Altere `OPENAI_API_KEY=sk-sua-chave-aqui` para sua chave real.

Se quiser notificacao por email, preencha tambem `EMAIL_USUARIO` e `EMAIL_SENHA_APP`.

## Executar

```cmd
INICIE O PROGRAMA.bat
```

O painel abre no navegador em `http://localhost:8501`.

## Solucao de Problemas

### "O CMD abre e fecha instantaneamente"

Isso ocorre quando ha erro antes do `pause`. Para ver o erro:

```cmd
# Abra o CMD manualmente (Win+R, cmd, Enter)
cd /d "C:\caminho\completo\ate\vagas-automation"
INSTALE CLICANDO AQUI.bat
```

### "Sem permissao de escrita"

`INSTALE CLICANDO AQUI.bat` e `INICIE O PROGRAMA.bat` testam se conseguem criar arquivos na pasta. Se estiver em `C:\` ou `Program Files`, execute como Administrador:
- Clique direito > "Executar como administrador"

### "Python nao encontrado apos instalacao"

O instalador do Python adiciona ao PATH. Se ainda assim nao funcionar:
- Feche e abra um novo CMD
- Ou execute `INSTALE CLICANDO AQUI.bat` novamente (ele tenta forcar o PATH)

### "Erro 429 (Too Many Requests) no LinkedIn"

O LinkedIn rate-limita a API Guest. O sistema ja tem `time.sleep(0.5)` entre paginas. Se continuar, espere alguns minutos e tente de novo.

### Playwright falhou

Nao e critico. Os scrapers usam `requests` + `BeautifulSoup`, Playwright e apenas para fallback. Ignore o erro e prossiga.