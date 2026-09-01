# ADR 0003 -- GG Oferta como primeiro consumidor ativo

## Status

Aceito (TASK-118A).

## Contexto

O César Core precisa de pelo menos um consumidor real para validar seus
contratos. A TASK-118A registrou essa identidade, mas não conectou o GG
Oferta ao Core.

## Decisão

`ApplicationId.GG_OFERTA` é registrado com `ApplicationState.ACTIVE`. Isso
habilita a identidade no registry, mas não cria por si só uma integração de
rede. A ligação do GG Oferta aos adapters e às futuras rotas de AI/Search
permanece fora do escopo já entregue pelas TASK-118A/118B.

## Consequências

Quando essa integração for implementada, GG Oferta já existirá no registry
com o estado correto, sem exigir migração de dados ou mudança de contrato.
