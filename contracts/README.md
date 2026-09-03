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

AI e Search usam o security scheme `ApplicationBearer`. `application_id` não
é parâmetro nem campo do body: ele é derivado da credencial. Erros de auth e
quota usam envelopes normalizados com request/correlation IDs. O endpoint
operacional `GET /metrics` exporta Prometheus text e fica deliberadamente fora
do OpenAPI de produto.

AI (118F): fornecer exatamente um de `prompt` ou `messages`. O legado `prompt`
vira uma única mensagem `user`; a lista tipada preserva ordem e roles
`system|user|assistant`. Lista vazia, conteúdo não textual/em branco, role
inválido, ambos os campos ou nenhum retornam 400 normalizado. Não há streaming,
tools nem multimodal. `AIRequest` interno contém somente mensagens normalizadas
e não herda o DTO HTTP. Conteúdo das mensagens não é registrado em telemetria.

Os DTOs públicos neutros de AI e Search fazem parte do OpenAPI. O
`OmniRouteClient` é uma dependência de transporte e não expõe diretamente
suas rotas upstream no OpenAPI do César Core.

Capabilities diferencia `search_general_web` de
`search_technical_documentation`: disponibilidade de um target especializado
não implica cobertura de busca Web geral.
