# ADR 0010 -- DTO HTTP público vs. requisição interna de domínio

## Status

Aceito (TASK-118A, correção de contrato antes do primeiro push).

## Contexto

`AIRequest`/`SearchRequest` carregavam `context: ApplicationContext`
como campo de nível superior do mesmo modelo que seria o corpo de uma
requisição HTTP. Ao mesmo tempo, `api/deps.py` já construía
`ApplicationContext` a partir de headers. Isso são duas fontes de
verdade para a identidade do chamador: um cliente HTTP poderia, em tese,
declarar seu próprio `application_id` dentro do corpo da requisição,
divergindo do que o Core resolveria via headers/dependencies.

## Decisão

Duas camadas, uma única fonte de verdade para identidade:

- **DTO HTTP público** (`AIRequestPayload`, `SearchRequestPayload`) --
  o que um endpoint aceitaria como corpo de requisição. Contém somente
  payload funcional (`prompt` ou `messages` em AI; `query` em Search) e `requirements`. **Nunca**
  contém `application_id` nem qualquer outro dado de identidade.
- **Requisição interna de domínio** (`AIRequest`, `SearchRequest`) --
  contém `context: ApplicationContext`. Desde a 118F, `AIRequest` não herda
  o DTO: contém apenas mensagens tipadas normalizadas, requirements e limite.
  O adapter HTTP converte prompt legado em uma mensagem user, ou preserva
  integralmente a lista tipada. `SearchRequest` mantém seu contrato anterior. É
  criada exclusivamente pelo próprio César Core, nunca deserializada
  diretamente do corpo de uma requisição HTTP.

Fluxo implementado pelas rotas públicas de AI/Search:

```text
HTTP (AIRequestPayload/SearchRequestPayload)
  -> Bearer auth/dependencies (api/deps.py)
  -> ApplicationContext confiável
  -> AIRequest/SearchRequest (internal)
  -> manager/provider
```

Desde a TASK-118E, `application_id` vem da credencial Bearer resolvida por
`security/`, nunca do header `X-Application-Id`. O header não faz parte do
OpenAPI e, se enviado, não altera a identidade autenticada. O contrato de
`ApplicationContext`/`AIRequest`/`SearchRequest` não precisou ser refeito.

`service`, `purpose` e `correlation_id` continuam sendo metadata
declarada pelo chamador (não uma identidade de segurança), sujeitos a
validação/policy futura -- a diferença é que `application_id`
especificamente precisa vir de algo que o chamador não pode forjar.

## Consequências

Cada endpoint de AI/Search declara `AIRequestPayload`/
`SearchRequestPayload` como corpo da requisição e `ApplicationContext`
como dependency separada; o Core monta o `AIRequest`/`SearchRequest`
interno combinando os dois antes de repassar a um manager/provider.
Nenhum cliente HTTP pode influenciar `application_id` através do corpo
da requisição.
