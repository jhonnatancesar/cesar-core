# ADR 0002 -- Identidade multi-aplicação via registry estático

## Status

Aceito (TASK-118A). `ApplicationContext` foi ampliado no mesmo TASK-118A
(ajuste de fundação pós-aprovação estrutural) -- ver ADR 0007 para o
contrato completo (`service`, `purpose`, `request_id`, `correlation_id`).

## Contexto

O César Core é infraestrutura compartilhável: mais de uma aplicação
consumidora poderá existir ao longo do tempo, cada uma com seu próprio
estado de habilitação.

## Decisão

`ApplicationId` (enum) identifica aplicações conhecidas. `ApplicationState`
(enum: `ACTIVE`/`RESERVED`) descreve se uma aplicação está habilitada a usar
o Core agora. Um registry estático (`applications/registry.py`) mapeia cada
`ApplicationId` a uma entrada `Application` com seu estado. `ApplicationContext`
carrega, por requisição, a identidade completa da execução:
`application_id`, `service` (processo/serviço chamador, ex.:
`collection_worker`), `purpose`, `request_id` e `correlation_id` -- ver
ADR 0007 para por que não há um `trace_id` separado.

## Consequências

Adicionar uma nova aplicação consumidora no futuro é uma entrada nova no
registry, não uma mudança estrutural. Nenhuma aplicação é descoberta
automaticamente -- cada uma precisa ser registrada explicitamente, na mesma
linha da política de fontes do GG Oferta (nenhuma fonte é integrada sem
Store Provider próprio).
