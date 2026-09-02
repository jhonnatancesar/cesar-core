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
- `GET /v1/capabilities`;
- `POST /v1/ai/generate`;
- `POST /v1/search`.

Os DTOs públicos neutros de AI e Search fazem parte do OpenAPI. O
`OmniRouteClient` é uma dependência de transporte e não expõe diretamente
suas rotas upstream no OpenAPI do César Core.

Capabilities diferencia `search_general_web` de
`search_technical_documentation`: disponibilidade de um target especializado
não implica cobertura de busca Web geral.
