# ADR 0005 -- HTTP como protocolo de contrato, documentado via OpenAPI

## Status

Aceito (TASK-118A).

## Contexto

O César Core precisa expor contratos estáveis e documentados para
aplicações consumidoras (hoje: GG Oferta), sem acoplar-se a nenhum SDK ou
biblioteca proprietária.

## Decisão

Todos os contratos externos do César Core são expostos via HTTP/JSON sobre
FastAPI, com o schema OpenAPI gerado automaticamente pela aplicação e
exportado para `contracts/openapi.json`. Os modelos Pydantic em `ai/`,
`search/`, `policy/` e `health/` são a fonte de verdade do formato desses
contratos.

## Consequências

Qualquer aplicação capaz de falar HTTP/JSON pode consumir o César Core, sem
depender de uma linguagem ou runtime específico. Mudança de contrato é
visível em `contracts/openapi.json` no diff do commit.
