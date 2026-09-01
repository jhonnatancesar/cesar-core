# Contratos

`openapi.json` é gerado a partir da aplicação FastAPI real (nunca escrito à
mão). Para regenerar após uma mudança de contrato:

```bash
python scripts/export_openapi.py
```

`tests/test_openapi_contract.py` garante que o arquivo commitado bate com o
schema gerado pela aplicação em tempo de teste.

## Superfície HTTP atual

O OpenAPI atual publica somente:

- `GET /health`;
- `GET /ready`;
- `GET /v1/capabilities`.

Os modelos em `ai/contracts.py` e `search/contracts.py` são contratos de
domínio preparados para as próximas rotas, mas ainda não fazem parte do
OpenAPI porque nenhum endpoint público de AI/Search foi registrado. O
`OmniRouteClient` também é uma dependência interna de transporte e não expõe
diretamente suas rotas upstream no OpenAPI do César Core.
