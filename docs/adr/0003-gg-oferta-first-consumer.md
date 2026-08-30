# ADR 0003 -- GG Oferta como primeiro consumidor ativo

## Status

Aceito (TASK-118A).

## Contexto

O César Core precisa de pelo menos um consumidor real para validar seus
contratos, mas esta fase não integra nenhum consumidor de fato (nenhuma
chamada HTTP do GG Oferta ao César Core é feita na TASK-118A).

## Decisão

`ApplicationId.GG_OFERTA` é registrado com `ApplicationState.ACTIVE`. Isso
apenas reserva a identidade e o estado no registry -- a integração real
(GG Oferta chamando o César Core via AIProviderManager/WebSearchManager)
é escopo de uma TASK-118 posterior, fora desta fundação.

## Consequências

Quando a integração real chegar, GG Oferta já existe no registry com o
estado correto, sem precisar de migração de dados ou mudança de contrato.
