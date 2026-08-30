# ADR 0002 -- Identidade multi-aplicação via registry estático

## Status

Aceito (TASK-118A).

## Contexto

O César Core é infraestrutura compartilhável: mais de uma aplicação
consumidora poderá existir ao longo do tempo, cada uma com seu próprio
estado de habilitação.

## Decisão

`ApplicationId` (enum) identifica aplicações conhecidas. `ApplicationState`
(enum: `ACTIVE`/`RESERVED`) descreve se uma aplicação está habilitada a usar
o Core agora. Um registry estático (`applications/registry.py`) mapeia cada
`ApplicationId` a uma entrada `Application` com seu estado. `ApplicationContext`
carrega, por requisição, qual aplicação está chamando, já com correlation ID
preparado.

## Consequências

Adicionar uma nova aplicação consumidora no futuro é uma entrada nova no
registry, não uma mudança estrutural. Nenhuma aplicação é descoberta
automaticamente -- cada uma precisa ser registrada explicitamente, na mesma
linha da política de fontes do GG Oferta (nenhuma fonte é integrada sem
Store Provider próprio).
