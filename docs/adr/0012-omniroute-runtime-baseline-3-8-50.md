# ADR 0012 -- Baseline de runtime/contrato do OmniRoute: 3.8.50 oficial, não 1f4dc830

## Status

Aceito (TASK-118B, correção antes de subir qualquer runtime).

## Contexto

ADR 0011 registrou como referência o commit `1f4dc830f3290a5507b5350417ae1547f825aefc`
(branch `release/v3.8.51`), aprovado durante o pré-flight para estudar a
arquitetura do OmniRoute. Ao tentar buildar esse commit localmente, dois
problemas apareceram:

1. Build local do Next.js/Turbopack travou o Docker Desktop por
   esgotamento de memória (máquina com só ~4 GB livres de 13,7 GB).
2. Investigação subsequente no Docker Hub (`diegosouzapw/omniroute`,
   290 tags) mostrou que **não existe imagem oficial `3.8.51`** -- a
   última tag numerada publicada é `3.8.50` (2026-08-27T04:23:13Z). O
   commit `1f4dc830` é datado 2026-08-30, **quatro dias depois** do
   commit que virou `v3.8.50` (`5458026c216f77a3da68ea49152dc33470cfe2cb`,
   2026-08-26) -- ou seja, `1f4dc830` é trabalho de manutenção ainda em
   andamento na branch `release/v3.8.51`, não lançado.

## Decisão

**Runtime/contract baseline da TASK-118B: OmniRoute 3.8.50 oficial.**

- Imagem: `diegosouzapw/omniroute:3.8.50`
- Digest: `sha256:085c57adf499a8aaa9f35ccde95c0df9c11bd9ecd18d6c9edbf3b68b8079ba9d`
- Commit associado (git tag `v3.8.50`): `5458026c216f77a3da68ea49152dc33470cfe2cb`
- Execução: `docker pull` por digest (nunca build local, nunca `:latest`/`:next`/`:main`).

`1f4dc830` é apenas **referência fora do baseline** -- usada para registrar a
evolução observada durante o pré-flight, nunca como contrato executável do
César Core. O fato de uma release posterior existir ou não no futuro não
altera o pin de compatibilidade decidido aqui.

## Diferenças reais levantadas (3.8.50 vs. 1f4dc830, 71 commits de distância)

Comparação `git diff` direta entre os dois commits, restrita às
superfícies que o César Core usa:

| Superfície | Diferença? | Detalhe |
|---|---|---|
| `GET /api/health` | **Nenhuma** | Diff vazio -- comportamento idêntico. |
| Autenticação (`isValidApiKey`, `extractApiKey`, `getApiKeyMetadata`, `requireManagementAuth`, login) | **Nenhuma relevante** | Único diff é null-safety para chamadas diretas em teste (sem `Request` real) -- irrelevante para um client HTTP real como o nosso. |
| `x-request-id` (lido por `compliance/index.ts` para auditoria interna do OmniRoute) | **Nenhuma** | Arquivo sem diff -- é o header que `OmniRouteClient.request()` propaga; seguro em 3.8.50. |
| `GET /v1/models` | **Interna, não estrutural** | 133+92 linhas mudam filtragem de "modelo gratuito" e cache do catálogo; o envelope de resposta (`data`/`object`) não muda. |
| `POST /v1/chat/completions` -- preservação de `x-correlation-id` | **Existe só em 1f4dc830** | Feature fora do baseline (`#11739`, `resolveIncomingCorrelationId`): 3.8.50 sempre gera um `reqId` novo via `generateRequestId()`, nunca preserva um `x-correlation-id` enviado pelo caller. A 118B é dona do transporte de baixo nível para `/v1/chat/completions` (`OmniRouteClient.chat_completions()`); somente o adapter que monta o payload de negócio fica para 118C. `OmniRouteClient` não usa `x-correlation-id` (ver ADR 0013), então essa divergência não bloqueia o transporte. |

## Consequência para correlation-id (César Core)

Ver ADR 0013 para o detalhamento completo: `correlation_id` do Core
continua sendo mantido ponta a ponta pelo próprio César Core (ADR 0007),
enviado ao OmniRoute como `x-request-id` (adaptação de transporte ao
contrato 3.8.50, idêntico em 3.8.50 e 1f4dc830), sem depender de eco --
confirmado ao vivo que o OmniRoute devolve seu **próprio** `x-request-id`
na resposta, capturado à parte em `OmniRouteResponse.upstream_request_id`.
Nenhum workaround foi criado para simular a feature `x-correlation-id`
de `/v1/chat/completions` que não pertence ao baseline 3.8.50.

## Consequências

Os testes de contrato reais da TASK-118B (`tests/test_omniroute_contract.py`)
rodam contra `diegosouzapw/omniroute:3.8.50` (por digest), não contra o
commit `1f4dc830`. Fixtures e expectativas correspondem ao comportamento
real observado em 3.8.50; nenhum teste pressupõe capacidades presentes
apenas fora desse baseline.
