# VAGAS AUTOMATION

Automacao de busca e analise de vagas executivas com IA.

## Estrutura

```
Vagas-Automation/
  app.py              Painel Streamlit
  INSTALE CLICANDO AQUI.bat           Instalacao 1-clique (Python + dependencias)
  INICIE O PROGRAMA.bat             Iniciar o painel
  check_vm.bat        Validacao pre-deployment
  .env.example        Template de configuracao
  config/             Termos de busca, geo IDs
  core/               Scrapers, IA, banco, notificacao
  docs/               Documentacao e tutoriais
  scripts/            Utilitarios de validacao
  tools/              Ferramentas auxiliares
```

## Primeiros passos

```cmd
INSTALE CLICANDO AQUI.bat
notepad .env                    # coloque sua chave OpenAI
INICIE O PROGRAMA.bat
```

## Documentacao

- `docs/ARCHITECTURE.md` — arquitetura completa
- `docs/TUTORIAIS/COMO_PERSONALIZAR.md` — guia para o cliente
- `docs/TUTORIAIS/COMO_RODAR_EM_VM.md` — setup em maquina limpa