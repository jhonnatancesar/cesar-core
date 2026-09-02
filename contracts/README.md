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
- `POST /v1/ai/generate`.

Os DTOs públicos de AI agora fazem parte do OpenAPI. Os modelos de Search
continuam internos até a TASK-118D. O `OmniRouteClient` é uma dependência de
transporte e não expõe diretamente suas rotas upstream no OpenAPI do César
Core.
