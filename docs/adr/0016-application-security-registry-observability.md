# ADR 0016 -- Segurança de aplicações, quotas e observabilidade

## Status

Aceito (TASK-118E).

## Contexto

O header declarativo `X-Application-Id` não podia ser uma autoridade de
segurança. Também era necessário preservar a separação de credenciais, impedir
o consumidor reservado de ganhar acesso acidental, limitar consumo antes do
upstream e observar uso sem registrar payloads ou segredos.

## Decisão

- `POST /v1/ai/generate` e `POST /v1/search` exigem Bearer auth. A credencial
  do GG Oferta é lida de `CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE` e
  comparada em tempo constante. Ausência/má configuração falha fechada com
  503; credencial ausente/inválida retorna 401 e `WWW-Authenticate: Bearer`.
- O registry é a fonte de estado e privilégio: `gg_oferta=ACTIVE`, client
  `ggoferta-core-client`, scopes AI/Search; `claudiao=RESERVED`, sem scopes e
  sem qualquer configuração de segredo.
- AI e Search usam credenciais OmniRoute independentes (`ggoferta-ai` e
  `ggoferta-search`), ambas de inferência e sem escopo administrativo.
- Quotas de requests/minuto são separadas por application/capability e
  verificadas antes de policy, manager e upstream. Excesso retorna 429 com
  `Retry-After`. O limiter atual é por processo; múltiplas réplicas exigirão um
  backend compartilhado antes de produção distribuída.
- `/metrics` exporta contadores/somas em Prometheus text. Labels públicas são
  operacionais e de baixa cardinalidade; credenciais, prompts, queries e
  conteúdo nunca entram em métricas.
- Eventos estruturados de sucesso registram application, service, purpose,
  request/correlation IDs, provider/model, latency, fallback e usage. Payload e
  segredo ficam fora do evento.
- Capabilities informa registry, autenticação e métricas sem listar o Claudião.
  Readiness exige auth da aplicação e credencial/probe OmniRoute específico
  para toda capability habilitada. Cada probe prova tanto a rejeição de uma
  chave inválida quanto a aceitação da chave configurada até a validação de um
  alvo deliberadamente inexistente, sem consumir modelo/provider.

## Consequências

Um `X-Application-Id: claudiao` não forja identidade: somente a credential
determina `application_id`. Rotação é feita substituindo atomicamente o arquivo
de segredo, pois ele é lido a cada autenticação. O endpoint de métricas não faz
parte do OpenAPI de produto. Nenhum deployment de produção, credential do
Claudião ou integração 118F/118G é criado nesta decisão.
