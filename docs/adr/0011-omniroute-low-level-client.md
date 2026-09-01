# ADR 0011 -- Client HTTP de baixo nível do OmniRoute (TASK-118B)

## Status

Aceito (TASK-118B). **Correção de baseline**: o commit
`1f4dc830f3290a5507b5350417ae1547f825aefc` citado abaixo era a
referência do pré-flight, mas não existe imagem oficial publicada para
ele -- o runtime/contrato real usado para validar este client é
`diegosouzapw/omniroute:3.8.50` (ver ADR 0012, que registra as
diferenças reais levantadas entre os dois).

## Contexto

TASK-118A reservou `omniroute/` como boundary, sem transporte real
(ADR 0006/0010). TASK-118B implementou `OmniRouteClient`, com config,
autenticação, timeout, erros, health, serialização/desserialização e
correlação. Os testes de contrato foram validados contra a imagem oficial
`diegosouzapw/omniroute:3.8.50`, fixada por digest; o commit de pré-flight
`1f4dc830f3290a5507b5350417ae1547f825aefc` não é o baseline executável.
Ver ADR 0012.

## Decisão

- **`config.py`** -- `OmniRouteConfig` (pydantic-settings, prefixo
  `CESAR_CORE_OMNIROUTE_`): `base_url`, `timeout_seconds` e
  `api_key_file` (caminho para um arquivo local com a chave -- nunca a
  chave em env var/código/Git, mesmo padrão `*_FILE` já usado no
  projeto).
- **`auth.py`** -- monta só o header `Authorization: Bearer <key>`.
- **`errors.py`** -- hierarquia de erros normalizados:
  `OmniRouteConnectionError`, `OmniRouteTimeoutError`,
  `OmniRouteAuthError` (401/403), `OmniRouteClientError` (outro 4xx),
  `OmniRouteServerError` (5xx). 401/403 nunca viram um 4xx genérico --
  guardrail explícito do plano-mestre da TASK-118 ("400/401/403 não são
  mascarados por cascata de fallback").
- **`models.py`** -- `OmniRouteHealth` (forma real de `GET /api/health`)
  e `OmniRouteResponse` (envelope genérico `status_code`, `body: dict` e
  `upstream_request_id` para qualquer rota autenticada).
- **`client.py`** -- `OmniRouteClient` expõe `health()` sem autenticação,
  `chat_completions()` e `search()` como conveniências de transporte, além
  de `request()` para chamadas autenticadas genéricas. Os métodos recebem
  payloads nativos como `dict` e não escolhem modelo, provider ou política.
  `correlation_id` é enviado como `x-request-id`; o identificador devolvido
  pelo OmniRoute é capturado separadamente como `upstream_request_id` (ADR
  0013). O módulo não importa `cesar_core.ai` nem `cesar_core.search`.

## Credencial mínima usada nos testes de contrato

A chave usada para os testes de contrato reais foi criada pelo mecanismo
oficial do próprio OmniRoute (`POST /api/auth/login` com a senha de
bootstrap local, seguido de `POST /api/keys` autenticado pela sessão),
sem escopo `manage` -- só acesso a `/v1/*`, a mesma credencial "certa"
já identificada na pesquisa da TASK-118 original. A chave em si nunca
foi impressa em código, chat ou log: foi gravada direto num arquivo
local (`.secrets/omniroute_api_key`, fora do Git) e só o caminho do
arquivo é conhecido pelo `OmniRouteConfig`.

## Fora de escopo (118C/118D)

Nenhuma regra de negócio, nenhum adapter de AI/Search, nenhuma seleção
de provider, nenhum combo do GG Oferta, nenhuma migração de fallback.
`ai/provider.py` e `search/provider.py` continuam sendo os únicos
boundaries de domínio -- um adapter concreto que *usa*
`OmniRouteClient` por baixo entra em `ai/providers/omniroute.py` e
`search/providers/omniroute.py` só na TASK-118C/118D.

## Consequências

O César Core já pode falar HTTP de verdade com um OmniRoute real,
validado por contract tests reais (não mockados) contra uma versão
pinada -- sem acoplar nenhuma regra de negócio de AI/Search a esse
transporte.
