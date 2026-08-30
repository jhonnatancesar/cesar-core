# ADR 0004 -- Claudião como consumidor futuro reservado

## Status

Aceito (TASK-118A).

## Contexto

O Claudião é um consumidor futuro já previsto, mas não deve ganhar nenhuma
integração funcional, URL, token, ou health check nesta fase -- o risco é
criar uma dependência operacional de algo que ainda não existe.

## Decisão

`ApplicationId.CLAUDIAO` é registrado com `ApplicationState.RESERVED`.
Nenhum código deste repositório assume que o Claudião está disponível ou
configurado. Não existe `CLAUDIAO_URL`, token, ou qualquer chamada de rede
relacionada a ele.

## Consequências

O contrato de identidade multi-aplicação (ADR 0002) já suporta o Claudião
entrar futuramente apenas mudando seu estado no registry, sem refatoração.
Até lá, ele é apenas um nome reservado.
