# ADR 0011 -- Client HTTP de baixo nível do OmniRoute (TASK-118B)

## Status

Aceito (TASK-118B). **Correção de baseline**: o commit
`1f4dc830f3290a5507b5350417ae1547f825aefc` citado abaixo era a
referência do pré-flight, mas não existe imagem oficial publicada para
ele -- o runtime/contrato real usado para validar este client é
`diegosouzapw/omniroute:3.8.50` (ver ADR 0012, que registra as
diferenças reais levantadas entre os dois).

## Contexto

TASK-118A reservou `omniroute/` como boundary, sem nenhum código real
(ADR 0006/0010). TASK-118B implementa esse transporte de verdade:
`omniroute/client` real, com config, autenticação, timeout, erros,
health, serialização/desserialização e correlation -- validado por
testes de contrato reais contra uma instância do OmniRoute rodando
localmente (repositório oficial `diegosouzapw/OmniRoute`, branch
`release/v3.8.51`, commit `1f4dc830f3290a5507b5350417ae1547f825aefc`
citado no pré-flight -- ver ADR 0012 para o baseline real usado,
buildada a partir do código-fonte nesse commit exato -- nunca `:latest`).

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
  e `OmniRouteResponse` (envelope genérico `status_code` + `body: dict`
  para qualquer rota autenticada).
- **`client.py`** -- `OmniRouteClient`: `health()` (sem autenticação,
  não depende de nenhum provider pago -- só prova que o processo
  OmniRoute está de pé) e `request(method, path, *, correlation_id,
  json=None, params=None)` (chamada autenticada genérica, propaga
  `correlation_id` como `x-request-id` -- header que o próprio OmniRoute
  lê para seu tracing/auditoria interno, dando correlação ponta a ponta
  real GG Oferta -> César Core -> OmniRoute). `request()` não sabe nada
  de AI/Search: é `omniroute/client.py` que não importa
  `cesar_core.ai`/`cesar_core.search`, e `OmniRouteClient` não expõe
  `complete()`/`search()` -- verificado por teste (`test_domain_separation.py`).

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
