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
  payload funcional (`prompt`/`query`) e `requirements`. **Nunca**
  contém `application_id` nem qualquer outro dado de identidade.
- **Requisição interna de domínio** (`AIRequest`, `SearchRequest`) --
  estende o DTO público adicionando `context: ApplicationContext`. É
  criada exclusivamente pelo próprio César Core, nunca deserializada
  diretamente do corpo de uma requisição HTTP.

Fluxo pretendido (ainda não implementado nesta TASK -- nenhuma rota de
AI/Search existe em 118A):

```text
HTTP (AIRequestPayload/SearchRequestPayload)
  -> auth/dependencies (api/deps.py::get_application_context)
  -> ApplicationContext confiável
  -> AIRequest/SearchRequest (internal)
  -> manager/provider
```

Nesta TASK, `security/` continua skeleton -- nenhuma autenticação real é
implementada. `get_application_context` resolve `application_id` a
partir do header `X-Application-Id`, o que é aceitável apenas para
teste/dev: **não é autoridade de segurança em produção**, porque
qualquer chamador pode declarar esse header livremente.

## Fonte futura de application_id em PROD

Na TASK-118E (autenticação real), `application_id` passa a vir da
identidade autenticada resolvida por `security/`, não mais do header
`X-Application-Id`. O contrato de `ApplicationContext`/`AIRequest`/
`SearchRequest` já está pronto para essa troca: só a implementação de
`get_application_context` muda, nenhum contrato precisa ser refeito.

`service`, `purpose` e `correlation_id` continuam sendo metadata
declarada pelo chamador (não uma identidade de segurança), sujeitos a
validação/policy futura -- a diferença é que `application_id`
especificamente precisa vir de algo que o chamador não pode forjar.

## Consequências

Um endpoint futuro de AI/Search declara `AIRequestPayload`/
`SearchRequestPayload` como corpo da requisição e `ApplicationContext`
como dependency separada; o Core monta o `AIRequest`/`SearchRequest`
interno combinando os dois antes de repassar a um manager/provider.
Nenhum cliente HTTP pode influenciar `application_id` através do corpo
da requisição.
