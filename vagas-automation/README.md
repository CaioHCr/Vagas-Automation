# VAGAS AUTOMATION

Automacao de busca e analise de vagas executivas com IA.

## Estrutura

```
Vagas-Automation/
  app.py              Painel Streamlit
  setup.bat           Instalacao 1-clique (Python + dependencias)
  run.bat             Iniciar o painel
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
setup.bat
notepad .env                    # coloque sua chave OpenAI
run.bat
```

## Documentacao

- `docs/ARCHITECTURE.md` — arquitetura completa
- `docs/TUTORIAIS/COMO_PERSONALIZAR.md` — guia para o cliente
- `docs/TUTORIAIS/COMO_RODAR_EM_VM.md` — setup em maquina limpa