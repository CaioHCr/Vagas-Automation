# COMO PERSONALIZAR

Tudo o que o cliente pode alterar sem mexer em codigo.

## Cargos e Keywords

**Onde:** Sidebar > CONFIGURACOES > Cargos-alvo / Keywords

**Efeito:** Os cargos sao usados nas buscas do LinkedIn e Gupy. As keywords sao injetadas no prompt da IA para avaliar aderencia.

**Formato:** Separado por virgulas. Ex:
```
COO,Diretor de Operacoes,Diretor Industrial,Head de Operacoes
```

## Localizacao

**Onde:** Sidebar > CONFIGURACOES > Localizacao (radio)

| Opcao | Escopo |
|---|---|
| Brasil | Vagas no Brasil (geoId=106057199) |
| LATAM | America do Sul (geoId=104514572) |
| Remoto (Worldwide) | Vagas remotas globais (sem filtro geografico, adiciona "remote" a busca) |

## Chave OpenAI

**Onde:** Sidebar > CONFIGURACOES > OpenAI Key

A chave deve ser do modelo `gpt-5.4-nano`. Obter em https://platform.openai.com/api-keys

## Email (Notificacao)

**Onde:** Sidebar > EMAIL (GMAIL SMTP)

Apos cada extracao, o sistema envia um resumo com as Top 5 vagas novas para o email configurado.

**Requer:** Senha de app do Google (16 caracteres). Gerar em https://myaccount.google.com/apppasswords

## Prompt do Sistema

**Onde:** Sidebar > PROMPT E CURRICULO > Prompt do Sistema

Arquivo: `prompt_sistema.txt`

Controla as regras que a IA usa para avaliar cada vaga. Edite para:
- Mudar o peso de certos criterios
- Adicionar novas regras de bonus/penalidade
- Ajustar tom e formato da justificativa

## Curriculo (CV)

**Onde:** Sidebar > PROMPT E CURRICULO > Curriculo

Arquivo: `curriculo.txt`

Injetado no user_content da chamada OpenAI. A IA compara cada vaga contra o curriculo para calcular o match score.

## Agendamento CRON

**Onde:** Sidebar > AGENDAMENTO

Define 2 horarios por dia para extracao automatica. O app precisa estar rodando (Streamlit aberto) para o scheduler funcionar.

## Geo IDs e Consultorias (JSON)

**Onde:** `config/termos_busca.json`

```json
{
  "localizacoes_ids": ["106057199"],
  "consultorias_ids": ["1681", "3476", ...],
  "localizacoes_disponiveis": { "Brasil": "106057199", ... }
}
```

- `localizacoes_ids`: geo IDs ativos (sincronizado pela sidebar)
- `consultorias_ids`: IDs de empresas headhunter para Fase 3
- `localizacoes_disponiveis`: mapeamento nome -> geo ID para o dropdown