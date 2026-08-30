# ADR 0013 -- correlation_id do César Core adaptado ao x-request-id do OmniRoute

## Status

Aceito (TASK-118B).

## Contexto

`OmniRouteClient` precisa propagar identidade de tracing do César Core
para o OmniRoute. O OmniRoute 3.8.50 lê o header `x-request-id` para o
seu próprio tracing/auditoria interno (`src/lib/compliance/index.ts`).
Testado ao vivo contra a instância real: enviar `x-request-id: <valor
do Core>` **não** faz o OmniRoute devolver esse mesmo valor -- a
resposta carrega o seu **próprio** `x-request-id`, gerado
independentemente (confirmado por probe real: enviado
`my-correlation-abc`, devolvido `ec6bb94a-c3fd-4c06-9890-06a5c752954e`).

## Decisão

A semântica interna do César Core (ADR 0007) **não muda**:

- `ApplicationContext.request_id` = identidade da execução individual
  recebida pelo César Core.
- `ApplicationContext.correlation_id` = correlação ponta a ponta,
  preservada quando fornecida, gerada quando ausente.

O que existe é uma **adaptação de transporte**, não uma equivalência
semântica: `OmniRouteClient.request()` (e `chat_completions()`/
`search()`, que o usam por baixo) envia `correlation_id` do Core como
`x-request-id` para o OmniRoute -- só porque é o mecanismo externo que o
OmniRoute 3.8.50 disponibiliza para carregar essa correlação através
dele, não porque os dois conceitos sejam a mesma coisa.

O `x-request-id` que o OmniRoute devolve na resposta é **capturado
separadamente**, nunca substitui nada do Core:

```python
class OmniRouteResponse(BaseModel):
    status_code: int
    body: dict[str, Any]
    upstream_request_id: str | None  # x-request-id devolvido pelo OmniRoute
```

`OmniRouteAuthError`/`OmniRouteClientError`/`OmniRouteServerError`
carregam o mesmo `upstream_request_id` (quando a resposta de erro tiver
o header), para que uma falha também preserve esse dado de telemetria.

## Por que não usar x-correlation-id

O OmniRoute 3.8.51 (ainda não lançado, ver ADR 0012) adiciona
preservação de um `x-correlation-id` fornecido pelo caller em
`/v1/chat/completions` especificamente. `OmniRouteClient` **não**
depende disso: nesta TASK o baseline é 3.8.50, que não tem essa
feature. Quando uma release oficial suportar isso, esta ADR deve ser
revisitada explicitamente -- não adotar silenciosamente um
comportamento que só existe numa branch não lançada.

## Consequências

Um adapter de domínio (118C/118D) que precisar do `upstream_request_id`
para logging/observabilidade o encontra em
`OmniRouteResponse.upstream_request_id` (sucesso) ou no atributo
`upstream_request_id` da exceção (erro) -- nunca precisa adivinhar ou
assumir que é igual ao `correlation_id` que o Core enviou.
