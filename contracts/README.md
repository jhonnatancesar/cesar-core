# Contratos

118G / ADR 0017: `max_results` limita a saída; SearXNG certificado para
`market_research` pode adquirir mais resultados antes do corte no OmniRoute.
Core garante também o cap final. Vazio continua sucesso, sem fallback.

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

Quota persistente (ADR 0018): excedente permanece `429 quota_exceeded`,
`Retry-After` e IDs normalizados, antes do upstream. Redis indisponível produz
`503 quota_store_unavailable`; configuração sem durabilidade exigida produz
`503 quota_store_misconfigured`, no mesmo envelope de segurança. Nenhum deles
é erro de provider nem quota excedida. `/ready` acrescenta `reason` opcional
com esses códigos, omitido quando ausente. Nenhum endpoint novo foi criado;
campos de sucesso AI/Search e security scheme não mudaram. OpenAPI regenerado
somente para documentar esse campo opcional no modelo existente de readiness.

Contracts históricos Core continuam em `test_omniroute_contract.py` e
`test_security_contract.py` (22). O fixture de quota usa namespace Redis de
teste único por caso; só testes não-contract usam um fake em memória.
`test_persistent_quota_contract.py` acrescenta sete cenários reais (concorrência,
TTL/corrupção, AOF, restart Core, Redis indisponível, OmniRoute e SearXNG recovery).
Mais dois cenários reais inicializam outro Redis com AOF desligado ou fsync
everysec: ambos respondem PING mas impedem AI/Search e degradam readiness com
reason explícito. Nenhum teste ou código Core executa CONFIG SET.
Executar exclusivamente com `scripts/run_118h_contracts.py core-persistence`
e stack descartável `scripts/stack_118h_dev.py up/down`; nunca contra PROD.

AI (118F): fornecer exatamente um de `prompt` ou `messages`. O legado `prompt`
vira uma única mensagem `user`; a lista tipada preserva ordem e roles
`system|user|assistant`. Lista vazia, conteúdo não textual/em branco, role
inválido, ambos os campos ou nenhum retornam 400 normalizado. Não há streaming,
tools nem multimodal. `AIRequest` interno contém somente mensagens normalizadas
e não herda o DTO HTTP. Conteúdo das mensagens não é registrado em telemetria.
`require_search_grounding=true` declara uma capability neutra: o Core solicita
Web Search ao OmniRoute, exige evidência estruturada e devolve
`grounding_requested`, `grounding_performed` e `grounding_sources`. Ausência de
busca ou evidência falha fechada; o cliente não escolhe provider.

Os DTOs públicos neutros de AI e Search fazem parte do OpenAPI. O
`OmniRouteClient` é uma dependência de transporte e não expõe diretamente
suas rotas upstream no OpenAPI do César Core.

Capabilities diferencia `search_general_web` de
`search_technical_documentation`: disponibilidade de um target especializado
não implica cobertura de busca Web geral.

O Control Plane da TASK-119 usa `/admin/api` e fica deliberadamente fora do
OpenAPI de produto: suas rotas são privadas, protegidas por sessão/CSRF e não
constituem contrato para aplicações consumidoras. A tela “Rotas” deriva seu
inventário do OpenAPI runtime, sem manter uma segunda lista manual.
