# ADR 0014 -- Central AI Gateway sobre o transporte OmniRoute

## Status

Aceito (TASK-118C, primeira fatia vertical).

## Contexto

A TASK-118B entregou transporte HTTP, mas não podia decidir modelo, política
de custo ou contrato público. Expor diretamente `/v1/chat/completions` faria
os consumidores dependerem do payload OmniRoute e misturaria transporte com
domínio.

## Decisão

- O contrato público é `POST /v1/ai/generate`, com
  `AIRequestPayload` no body e `ApplicationContext` resolvido separadamente.
- O cliente nunca envia application, service, purpose, request ID ou
  correlation ID no body. Esses valores são controlados pelo César Core;
  `correlation_id` é adaptado pelo transporte conforme ADR 0013.
- `AIPolicy` resolve `(application_id, purpose, service_class)` para um
  `AIModelTarget`. Uma regra de purpose `*` é fallback explícito de policy,
  não fallback de provider.
- `FREE_ONLY` bloqueia alvos marcados como pagos e `max_tokens` respeita o
  limite do alvo. A policy falha fechada quando não existe regra.
- `AIManager` aplica policy e mede latência.
- `OmniRouteAIProvider` é o único adapter de AI que importa
  `OmniRouteClient`. Ele traduz o prompt para chat completions e normaliza
  falhas, content, model, provider, usage, fallback e upstream request ID.
- Não há retry em outro modelo/provider no César Core. O roteamento e o
  fallback upstream continuam pertencendo ao OmniRoute.

## Configuração inicial

`AIConfig` usa o prefixo `CESAR_CORE_AI_`. AI permanece desligada por padrão.
Quando habilitada, `DEFAULT_MODEL` atende todas as classes, com overrides
opcionais para economy, standard e quality. A configuração inicial registra
somente GG Oferta; Claudião continua reservado.

O endpoint não aceita modelo nem provider no DTO público. Essa escolha é
sempre resultado de configuração e policy interna.

### Semântica de max_tokens

`max_tokens` é um hard cap do contrato público, além do teto aceito pela
policy. Antes de executar, a policy exige um alvo fixo marcado
`enforces_max_tokens`; aliases dinâmicos não podem receber essa marca porque o
provider/model resolvido pode mudar. Sem essa garantia explícita, a chamada é
rejeitada antes do upstream. O adapter ainda encaminha o valor e só aceita
sucesso quando o usage traz `completion_tokens <= max_tokens`; usage ausente ou
acima do limite é resposta upstream incompatível (502), nunca sucesso silencioso.

A validação real com OmniRoute 3.8.50 encontrou exatamente essa proteção em
ação: `auto/best-free`/`auto/best-fast` resolveu para `opencode/big-pickle`,
ignorou tanto `max_tokens` quanto `max_completion_tokens` e reportou usage
superior. Uma chamada direta ao upstream OpenCode confirmou que a violação é do
próprio `big-pickle`, não do adapter nem do repasse do OmniRoute. Esse alvo pode
atender chamadas sem hard cap, mas a policy não o executa quando a chamada
declara `max_tokens`.

No mesmo runtime, o alvo fixo `oc/mimo-v2.5-free` comprovou enforcement real:
`max_tokens=128` chegou intacto ao OmniRoute e o upstream terminou com usage de
completion abaixo do cap. A configuração de runtime só pode definir
`MODEL_ENFORCES_MAX_TOKENS=true` para um alvo fixo coberto por esse tipo de
contract test.

### Autenticação do runtime local

Os contract tests de autenticação exigem `REQUIRE_API_KEY=true` no OmniRoute.
Com `false`, o OmniRoute 3.8.50 registra a chave inválida e permite fallback
anônimo em `/v1/chat/completions`; essa configuração não prova a fronteira
César Core -> OmniRoute e não é aceita para a validação da TASK-118C.

## Health e capabilities

AI e OmniRoute aparecem como `available` apenas quando AI está habilitada e
há modelo padrão. Nesse caso, `/ready` executa o health real do OmniRoute e
prova que `/v1/chat/completions` rejeita uma credencial inválida. Falha de
configuração, conexão, health ou autenticação não obrigatória deixa readiness
`degraded`.

## Consequências

Consumidores dependem de um contrato neutro, e trocar o gateway não exige
alterar o DTO público. A primeira configuração suporta policy wildcard por
purpose; regras específicas podem ser injetadas diretamente em `AIPolicy`
sem modificar manager, adapter ou endpoint.
