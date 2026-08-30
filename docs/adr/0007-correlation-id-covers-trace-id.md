# ADR 0007 -- correlation_id cobre o papel de trace_id nesta V1

## Status

Aceito (TASK-118A, ajuste de fundação pós-aprovação estrutural).

## Contexto

`ApplicationContext` precisa carregar identidade ponta a ponta de uma
execução. Um dos requisitos era decidir entre manter `trace_id` como
campo separado de `correlation_id`, ou unificar os dois -- sem criar
dois identificadores redundantes para a mesma correlação.

## Decisão

`ApplicationContext` usa **somente** `correlation_id`. Não existe campo
`trace_id` separado nesta V1: `correlation_id` assume esse papel --
identifica a correlação ponta a ponta de uma execução através de toda a
cadeia de chamadas (GG Oferta -> César Core -> OmniRoute -> provider).

`request_id` continua sendo um campo distinto: identifica esta
requisição individual (um hop específico), nunca é reaproveitado de um
header, e é gerado pelo próprio César Core a cada requisição (ver
`telemetry/request_id.py`). `correlation_id`, ao contrário, é reaproveitado
quando o chamador o envia (ver `telemetry/correlation.py`), justamente
para se propagar por toda a cadeia.

## Consequências

Se uma necessidade real de distinguir "trace" de "correlation" aparecer
no futuro (ex.: integração com um sistema de tracing distribuído que
exija um `trace_id` em formato próprio, como W3C Trace Context), esta
ADR precisa ser revisitada explicitamente -- não introduzir o campo de
volta silenciosamente.
