# ADR 0004 -- Claudião como consumidor futuro reservado

## Status

Aceito (TASK-118A).

## Contexto

O Claudião é um consumidor previsto, mas ainda não possui integração
funcional, URL, token ou health check. Criar esses elementos antes de existir
um consumidor real produziria uma dependência operacional especulativa.

## Decisão

`ApplicationId.CLAUDIAO` é registrado com `ApplicationState.RESERVED`.
Nenhum código deste repositório assume que o Claudião está disponível ou
configurado. Não existe `CLAUDIAO_URL`, token, ou qualquer chamada de rede
relacionada a ele.

A TASK-118E preserva essa decisão: o registry mantém o `client_id` reservado
para compatibilidade estrutural, mas não existe configuração `*_FILE`, segredo
funcional ou scope autorizado para o Claudião.

## Consequências

O contrato de identidade multi-aplicação (ADR 0002) já suporta o Claudião
entrar futuramente apenas mudando seu estado no registry, sem refatoração.
Até lá, ele é apenas um nome reservado.
