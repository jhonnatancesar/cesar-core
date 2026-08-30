# ADR 0009 -- ApplicationContext vs Requirements: fronteira de responsabilidade

## Status

Aceito (TASK-118A, correção de contrato antes do primeiro push).

## Contexto

`Requirements` tinha um campo `service: ServiceKind` (`ai`/`search`) e
`ApplicationContext` tem um campo `service: str` (ex.:
`collection_worker`). Dois campos de mesmo nome, com significados
diferentes, em contratos que viajam juntos dentro do mesmo `AIRequest`/
`SearchRequest` -- exatamente a "metadata espalhada" que a TASK-118A
pediu para eliminar, e uma fonte real de confusão (qual `service` é
qual?).

## Decisão

A fronteira final é:

- **`ApplicationContext`** = quem está chamando + por quê + identidade/
  tracing da chamada: `application_id`, `service` (processo/serviço
  chamador), `purpose`, `request_id`, `correlation_id`.
- **`Requirements`** = quais capacidades/qualidade/custo a execução
  exige: `service_class`, `cost_policy` nesta fase (capacidades
  específicas como `structured_output`, `reasoning`, `vision`,
  `tool_calling` ficam para quando uma TASK futura precisar delas de
  fato -- não foram adicionadas especulativamente aqui).

`ServiceKind` (`ai`/`search`) foi removido: qual gateway está sendo
chamado já é dado pelo tipo do request (`AIRequest` vs `SearchRequest`),
não precisa de um campo redundante dentro de `Requirements` para
repetir essa informação.

## Consequências

Não há mais dois campos `service` com significados diferentes dentro do
mesmo request. Se no futuro for necessário expressar "qual gateway"
como dado explícito (por exemplo, para um endpoint genérico que aceite
ambos), isso deve ser um campo com outro nome, decidido explicitamente
-- não a reintrodução de `Requirements.service`.
