# VAGAS AUTOMATION — DOCUMENTACAO ARQUITETURAL

## Estrutura de Pastas

```
projeto/
├── vagas.db                         # SQLite (pasta pai do projeto)
│
└── vagas-automation/
    ├── app.py                       # Streamlit: painel + 3 fases + CRON
    ├── setup.bat                    # Instalacao completa (Python incluso)
    ├── run.bat                      # Atalho para iniciar o painel
    ├── requirements.txt             # Dependencias Python
    ├── prompt_sistema.txt           # System prompt OpenAI (regras de scoring)
    ├── curriculo.txt                # CV do candidato (injetado no user_content)
    ├── execution.log                # Log acumulado de todas as execucoes
    ├── DOCUMENTATION.md             # Este arquivo
    │
    ├── config/
    │   └── termos_busca.json        # Geo IDs, consultorias IDs
    │
    └── core/
        ├── database.py              # SQLite: schema, CRUD, hide/show
        ├── intelligence.py          # OpenAI + Jina Reader + pre-filter
        ├── notifier.py              # Email SMTP (Gmail) com resumo HTML
        ├── scraper_ln.py            # Motor HTTP LinkedIn Guest API
        ├── scraper_gupy.py          # Motor HTTP Gupy API
        ├── logger.py                # Logging com rotacao (5MB max)
        └── config.py                # Pydantic Settings (.env loader)
```

## Pipeline de Extracao (3 Fases)

O botao "INICIAR EXTRACAO" ou o agendador CRON disparam 3 fases em sequencia,
cada uma com feedback visual via `st.status()`:

### Fase 1: LinkedIn Mercado Aberto
- `fetch_linkedin_jobs_http(lista_empresas=None)`
- URL sem `f_C` (busca irrestrita em todas as empresas)
- Itera sobre `localizacoes_ids`: primeiro `106057199` (Brasil), depois `104514572` (America do Sul)
- Pagina com offset 0, 25, 49 (ate 50 vagas), com `time.sleep(0.5)` entre paginas
- Aplica filtro geografico por dominio: so aceita br/mx/ar/cl/co/pe.linkedin.com
- Aplica pre-filtro por titulo + Jina Reader + analise OpenAI

### Fase 2: Gupy
- `fetch_gupy_jobs()`
- Busca em `portal.gupy.io` e `employability-portal.gupy.io`
- Usa descricao direta da API JSON (sem Jina Reader — evita timeouts)
- Aplica filtro local + pre-filtro + analise OpenAI

### Fase 3: LinkedIn Consultorias Executivas
- `fetch_linkedin_jobs_http(lista_empresas=consultorias_str)`
- URL com `&f_C=1681,3476,...` (13 headhunters)
- Mesmo motor da Fase 1, porem filtrando apenas vagas dessas empresas

### Motor de IDs de Consultorias (f_C)

A API Guest do LinkedIn aceita o parametro `f_C` para filtrar por empresa.
As IDs sao carregadas do `config/termos_busca.json` e consolidadas em string
unida por virgulas antes de passar para a URL.

## Kanban e Persistencia

### Banco de Dados (SQLite)
- Arquivo: `../vagas.db` (pasta pai do projeto — persiste entre execucoes)
- Tabela `vagas` com colunas:

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | TEXT PK | Hash MD5 do link |
| data_captura | TEXT | Timestamp ISO |
| cargo | TEXT | Titulo da vaga |
| empresa | TEXT | Nome da empresa |
| plataforma | TEXT | LinkedIn ou Gupy |
| score_aderencia | INTEGER | 0-100 |
| justificativa | TEXT | Explicacao da IA (max 15 palavras) |
| status_candidatura | TEXT | Novas / Vou Aplicar / Aplicado / Excluir |
| oculta | INTEGER | 0=visivel, 1=oculta (nao renderiza card) |
| link | TEXT | URL da vaga |
| descricao | TEXT | Texto limpo via Jina ou API (max 5000 chars) |
| bloqueado_requer_sessao | INTEGER | 1=login wall detectado |

### Logica de Ocultacao (4 Travas Operacionais)

1. **Memoria**: `vaga_existe()` — se o hash do link ja esta no DB, pula
2. **Pre-filtro**: `pre_filter_vaga()` — se o titulo nao tem radical executivo ou tem area incompativel, registra como Excluir + oculta
3. **Login wall**: se Jina retorna pagina de login, registra como `bloqueado_requer_sessao=1` + Excluir + oculta
4. **Threshold**: se `score_aderencia < 50`, status = Excluir + `oculta=1`

Vagas ocultas (`oculta=1`) nao aparecem nos cards do kanban, mas ficam visiveis
na aba MEMORIA (que usa `get_all_vagas()` sem filtro de oculta).

### Painel de Cards
- 4 colunas com cores: NOVAS (laranja), VOU APLICAR (verde), APLICADO (azul), EXCLUIR (vermelho)
- Cada card: cargo, empresa, score %, dropdown inline para mover entre colunas
- Expander DETALHES: justificativa, link, descricao (truncada ate a linha URL Source)
- Botao LIMPAR TUDO na coluna EXCLUIR — chama `hide_all_vagas('Excluir')`,
  oculta todas do painel mas mantem no banco
- Botao Re-analisar N vaga(s) com erro no topo da aba VAGAS

### Scoring (OpenAI)
- Modelo: `gpt-5.4-nano` com `response_format={"type": "json_object"}`
- System prompt em `prompt_sistema.txt` com 4 regras:
  1. Penalizacao severa (score <= 30) — setor incompativel
  2. Aderencia parcial (31-69) — setor ok mas senioridade abaixo
  3. Alta aderencia (70-100) — cargo-alvo + setor prioritario + palavras-chave
  4. Bonus de localizacao: +5 se Presencial/Hibrida em SP, Sul ou Sudeste
- Output JSON: `{"score_aderencia": int, "justificativa": "string"}`
- Justificativa limitada a 15 palavras

## Configuracoes

### `.env` (via sidebar)
```
OPENAI_API_KEY=sk-...
CARGOS_ALVO=COO,Diretor de Operacoes,Diretor Industrial,...
KEYWORDS_EXECUTIVAS=Turnaround,Excelencia Operacional,Supply Chain,...
LOCALIZACAO_FILTRO=Brasil
EMAIL_USUARIO=seu@gmail.com
EMAIL_SENHA_APP=abcd1234efgh5678
```
Editavel diretamente na sidebar do Streamlit. Os campos `CARGOS_ALVO` e
`KEYWORDS_EXECUTIVAS` tem aspas simples/duplas removidas automaticamente
ao salvar. `EMAIL_SENHA_APP` deve ser uma senha de app Google (16 letras),
nao a senha normal da conta.

### `config/termos_busca.json`
```json
{
  "localizacoes_ids": ["106057199", "104514572"],
  "consultorias_ids": [
    "1681",     "3476",     "3741",     "53013",    "13131",
    "5417",     "3863592",  "349389",   "49291",    "5652",
    "157317",   "3975",     "3020263"
  ]
}
```
- `106057199` = Brasil
- `104514572` = America do Sul
- Consultorias: Robert Half, Michael Page, Korn Ferry (6 subsidiaries),
  Egon Zehnder, Spencer Stuart, Heidrick & Struggles, Talenses

### `prompt_sistema.txt`
Regras de classificacao + matriz de palavras-chave + bonus de localizacao.
Editavel na sidebar. Se o arquivo nao existir, usa prompt fallback interno.

### `curriculo.txt`
Texto livre do CV do candidato. Injetado no `user_content` da OpenAI.
Editavel na sidebar.

## Sistema de Agendamento (CRON Local)

### Arquitetura
- Biblioteca: `schedule>=1.2`
- Thread separada: `threading.Thread(target=_scheduler_loop, daemon=True)`
- A thread executa `schedule.run_pending()` a cada 30 segundos
- Nao interfere na reatividade do Streamlit (nao toca em `st.session_state`)
- Morre quando o processo Streamlit e encerrado (`daemon=True`)

### Configuracao na Sidebar
- 2 campos `st.time_input` para definir horarios (padrao 06:00 e 18:00)
- Botao ATIVAR AGENDADOR: chama `schedule.clear()` + registra novos horarios
  + inicia a daemon thread (se ja existe, so substitui os horarios)
- Botao PARAR AGENDADOR: `schedule.clear()` — a thread continua rodando
  mas sem jobs agendados
- Indicador: "Agendador ativo nos horarios: 06:00, 18:00"

### Pipeline Disparado
O CRON executa as mesmas 3 fases do botao manual, mas sem callback de UI
(os scrapers recebem `ui_callback=None` e logs vao apenas para `execution.log`):
`fetch_linkedin_jobs_http(open)` -> `fetch_gupy_jobs()` -> `fetch_linkedin_jobs_http(consultorias)`

### Limitacoes
- O app precisa estar rodando para o agendador funcionar
- Se o computador estiver desligado/suspenso no horario agendado, o job e
  perdido (schedule nao faz catch-up)
- Para agendar em minutos especificos, use o formato `"HH:MM"` no `st.time_input`

## Sidebar do Streamlit

A barra lateral (recolhida por padrao) contem:

### CONFIGURACOES
- OpenAI Key (password field)
- Cargos-alvo (text area)
- Keywords (text area)
- Localizacao (text input)
- Botao SALVAR CONFIGS → escreve no `.env` e faz `st.rerun()`

### AGENDAMENTO (CRON)
- Horario 1 (time_input, padrao 06:00)
- Horario 2 (time_input, padrao 18:00)
- ATIVAR AGENDADOR → inicia schedule
- PARAR AGENDADOR → limpa schedule
- Indicador de status

### PROMPT E CURRICULO
- Editor de curriculo.txt (text area, 200px)
- Botao SALVAR CURRICULO
- Editor de prompt_sistema.txt (text area, 250px)
- Botao SALVAR PROMPT

### UTILITARIOS
- LIMPAR LOGS → limpa `execution.log`

## Inicializacao e Dependencias

### Setup automatico (Windows — PC sem nada instalado)
```bash
cd vagas-automation
setup.bat
```
O script:
1. Detecta Python. Se nao existir, baixa e instala Python 3.12.9 automaticamente:
   - Tenta `winget install Python.Python.3.12` (Windows 10 1809+)
   - Se winget nao existe, baixa o installer EXE de `python.org` via `curl`
     (built-in do Windows 10+) e instala com `/quiet InstallAllUsers=1 PrependPath=1`
2. Cria `venv` e instala dependencias de `requirements.txt`
3. Instala Chromium via `playwright install chromium`
4. Cria `config/termos_busca.json` com valores padrao se nao existir
5. Cria `.env` com placeholders se nao existir (avisa usuario para editar a chave OpenAI)
6. Valida que todas as bibliotecas criticas importam

### Instalacao manual
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

### Executar
```bash
python -m streamlit run app.py
# ou clique duas vezes em run.bat
```

### Dependencias (requirements.txt)
```
streamlit>=1.30
pandas>=2.0
playwright>=1.40
requests>=2.31
python-dotenv>=1.0
openai>=1.0
pydantic>=2.0
pydantic-settings>=2.0
beautifulsoup4>=4.12
schedule>=1.2
```

## Observacoes Tecnicas

- O scraper LinkedIn usa a API Guest (`/jobs-guest/jobs/api/seeMoreJobPostings/`),
  nao requer autenticacao, mas e rate-limited e retorna resultados regionais
- `geoId=106057199` (Brasil) forcado na URL + dominio `br.linkedin.com` garantem
  que os resultados sejam Brasileiros. `geoId=104514572` adiciona America do Sul
- Filtro geografico secundario bloqueia dominios de paises fora do escopo
  (ve.linkedin.com, ec.linkedin.com, gy.linkedin.com, sr.linkedin.com, etc.)
- Jina Reader (`r.jina.ai/{url}`) e usado apenas nas fases 1 e 3 (LinkedIn);
  Gupy usa descricao direta da API (`descricao_direta`) para evitar timeouts
- O banco SQLite fica em `../vagas.db` (pasta pai) para persistir entre execucoes
- Logs usam `RotatingFileHandler` com limite de 5MB. Quando estoura, o arquivo
  e renomeado para `execution.log.1` e um novo `execution.log` e criado.
  `clear_logs()` tambem remove o backup `.1`
- `setup.bat` e `run.bat` testam permissao de escrita no primeiro passo. Se o
  usuario tentar rodar de `C:\` ou outra pasta protegida sem Admin, exibem
  instrucao para executar como Administrador
- Ambos os batch files usam `cd /d "%~dp0"`, o que os torna resilientes a
  mudancas de nome de pasta ou localizacao — funcionam de qualquer lugar
- Toda extracao e protegida por 4 travas: duplicidade, pre-filtro, login wall, threshold
- Interface sem emojis, tipografica, com sidebar recolhida por padrao
- Apos cada extracao (manual ou agendada), um e-mail de resumo e disparado via SMTP
  Gmail com as Top 5 vagas novas ordenadas por score, desde que EMAIL_USUARIO e
  EMAIL_SENHA_APP estejam configurados no .env
- `EMAIL_SENHA_APP` deve ser uma senha de app do Google (gerada em
  https://myaccount.google.com/apppasswords), nao a senha normal da conta
