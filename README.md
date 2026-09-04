# César Core

Infraestrutura central multi-aplicação de IA, Web Search, políticas de uso e
identidade de aplicação consumidora. O repositório é independente do GG
Oferta e contém o transporte HTTP real de baixo nível para o OmniRoute.

## Estado atual

O projeto concluiu a fundação (**TASK-118A**), o transporte OmniRoute
(**TASK-118B**) e as primeiras fatias dos gateways centrais de AI
(**TASK-118C**), Web Search (**TASK-118D**) e segurança/observabilidade
(**TASK-118E**). Estão disponíveis:

- registry de aplicações e `ApplicationContext`;
- contratos internos e boundaries separados de AI e Search;
- políticas de classe de serviço e custo;
- endpoints `/health`, `/ready` e `/v1/capabilities`;
- `OmniRouteClient` para `/api/health`, `/v1/chat/completions` e `/v1/search`;
- autenticação Bearer, timeout, correlação e erros normalizados do transporte.
- policy AI por application/purpose/service class e restrição de custo;
- `AIManager`, adapter OmniRoute e `POST /v1/ai/generate`;
- resposta AI normalizada com usage, modelo, provider e IDs de telemetria.
- policy Search por application/purpose/service class, `FREE_ONLY` e limite;
- `SearchManager`, adapter OmniRoute e `POST /v1/search`;
- resposta Search normalizada com resultados, usage, provider, cache e tracing.
- autenticação Bearer aplicação→Core, registry com scopes e quota pré-upstream;
- credenciais Core→OmniRoute independentes para AI e Search;
- métricas Prometheus em `/metrics` e tracing estruturado sem payload/segredos.

As integrações do GG Oferta de AI (118F) e Search (118G) estão implementadas,
aprovadas e publicadas em `main`, com rollout desligado por padrão. A 118H
concluiu a validação DEV e foi aprovada; deployment de produção não foi
executado nem está autorizado. Ver `docs/task-118h-rollout-resilience.md`.
Cada gateway aparece como `not_configured` enquanto
sua flag estiver falsa ou faltar seu alvo padrão; OmniRoute fica `available`
quando AI ou Search estiver configurado.

## Escopo

**TASK-118A** (fundação, concluída): estrutura de projeto, identidade de aplicações
(`gg_oferta` = ACTIVE, `claudiao` = RESERVED), `ApplicationContext` completo
(application/service/purpose/request_id/correlation_id), contratos neutros
de AI/Search com boundary de provider próprio para cada um (sem chamadas
reais), modelos de política (`service_class`, `cost_policy`) e os endpoints
`/health`, `/ready` e `/v1/capabilities` -- semântica exata em ADR 0008.

**TASK-118B** (transporte OmniRoute, concluída): `OmniRouteClient` real -- config,
autenticação, timeout, erros, health, serialização/desserialização,
correlation. Transporte de baixo nível pronto para `/api/health`,
`/v1/chat/completions` e `/v1/search` (`health()`, `chat_completions()`,
`search()`) -- validado por testes de contrato reais contra
`diegosouzapw/omniroute:3.8.50` rodando localmente por digest (ver ADR
0011/0012/0013). Ainda sem regras de negócio, sem adapters de AI/Search
(quem monta o payload de negócio e escolhe modelo/provider é 118C/118D),
sem configuração de Gemini/Groq/OpenRouter, sem o agente Claudião, sem
deployment em produção.

**TASK-118C** (Central AI Gateway, concluída): contrato neutro, `AIManager`,
policy, adapter OmniRoute, usage/tracing, hard cap certificado de `max_tokens`
e `POST /v1/ai/generate` (ADR 0014).

**TASK-118D** (Central Web Search Gateway, concluída): contrato neutro,
`SearchManager`, policy por aplicação/purpose/classe, adapter OmniRoute,
usage/tracing, semântica explícita de fallback e `POST /v1/search` (ADR 0015).
A migração do Market Research foi entregue posteriormente pela 118G.

**TASK-118E** (Security, Registry & Observability): `gg_oferta` autenticado por
credencial Bearer em arquivo e autorizado para AI/Search; `claudiao` continua
`RESERVED`, sem credential e sem scopes. Quotas por aplicação/capability são
aplicadas antes do manager/upstream. Métricas e logs estruturados agregam
application/service/purpose, IDs, provider/model, latência, fallback e usage
sem registrar prompts, queries ou segredos (ADR 0016).

**TASK-118F/118G** (concluídas e publicadas): messages tipadas retrocompatíveis,
integração AI no GG Oferta e Search via SearXNG, com enriquecimento Firecrawl
separado. Commits Core: `95b6996` (118F) e `3578f2b` (118G); GG Oferta:
`c383fdc` (118F) e `80dc135` (118G). Publicação de código não equivale a deploy.

**TASK-118H** (validação DEV concluída e aprovada): restart real do Core,
recuperação de dependências, rollback AI/Search e runbook operacional. Ver
`docs/task-118h-rollout-resilience.md`. Nenhum rollout PROD autorizado.

## Estrutura

```text
src/cesar_core/
  api/            aplicação FastAPI e rotas HTTP
  applications/   ApplicationId, ApplicationState, ApplicationContext, registry
  ai/             contrato, policy, manager e adapter OmniRoute de AI
  search/         contrato, policy, manager e adapter OmniRoute de Search
  omniroute/      client HTTP de baixo nível (health, chat completions, search)
  policy/         service_class, cost_policy, requirements
  security/       autenticação, credentials, autorização e quotas
  telemetry/      IDs, tracing estruturado e métricas Prometheus
  health/         lógica de health/readiness/capabilities
  config/         settings do processo
```

`ai/` e `search/` nunca compartilham uma interface de provider: cada um tem a
sua (`ai/provider.py`, `search/provider.py`). Os adapters vivem em
`ai/providers/omniroute.py` e `search/providers/omniroute.py`; ambos usam o
transporte de `omniroute/client.py` -- ver ADR 0006, 0014 e 0015.

Cada domínio (`ai/`, `search/`) expõe duas camadas de contrato (ADR
0010): `AIRequestPayload`/`SearchRequestPayload` é o DTO HTTP público
(sem identidade do chamador no corpo); `AIRequest`/`SearchRequest` é a
requisição interna, criada pelo Core combinando esse payload com um
`ApplicationContext` já resolvido. `ApplicationContext` e `Requirements`
também têm fronteira própria (ADR 0009): contexto é quem/por quê/
tracing, requirements é capacidade/qualidade/custo.

## Desenvolvimento local

```bash
pip install -e ".[dev]"
pytest -m "not contract"   # suíte padrão, não depende de infra viva
ruff check .
```

Testes de contrato reais contra o OmniRoute (`pytest -m contract`) só
rodam quando `.secrets/omniroute_api_key` existe; sem isso, são pulados
automaticamente -- ver ADR 0011.

A configuração de exemplo está em `.env.example`. Nenhuma chave deve ser
colocada no `.env`: os campos `*_FILE` apontam para arquivos locais fora do
Git. A chamada aos gateways exige `Authorization: Bearer <credential>`; o Core
deriva `application_id` dessa credencial e ignora qualquer tentativa de
declará-lo no payload ou em `X-Application-Id`.

Para habilitar o endpoint AI, configure ao menos:

```env
CESAR_CORE_AI_ENABLED=true
CESAR_CORE_AI_DEFAULT_MODEL=<modelo disponível no OmniRoute>
CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE=.secrets/ggoferta-ai
CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE=.secrets/ggoferta-core-client
```

O modelo não é aceito no body público: ele é escolhido pela policy interna.

Na TASK-118F, AI aceita **exatamente um** formato de entrada (além de
`requirements` e do `max_tokens` opcional): `{"prompt":"texto"}` ou
`{"messages":[{"role":"system","content":"instrução"},{"role":"user","content":"texto"}]}`.
`prompt` permanece compatível e vira uma mensagem `user`, sem alterar seu texto.
`messages` aceita somente `system`, `user` e `assistant`, com conteúdo textual
não vazio, preservando roles e ordem até o OmniRoute, sem concatenação.
Ambos, nenhum ou mensagens inválidas retornam 400 `ai_invalid_request`, antes
do upstream, sem ecoar conteúdo. Auth, quota e policies continuam obrigatórias.
`ECONOMY_MODEL`, `STANDARD_MODEL` e `QUALITY_MODEL` permitem overrides por
classe de serviço. `FREE_ONLY` rejeita um alvo marcado como pago.

Para habilitar o endpoint Search, configure ao menos:

```env
CESAR_CORE_SEARCH_ENABLED=true
CESAR_CORE_SEARCH_DEFAULT_PROVIDER=
CESAR_CORE_SEARCH_TECHNICAL_DOCUMENTATION_PROVIDER=context7
CESAR_CORE_OMNIROUTE_SEARCH_API_KEY_FILE=.secrets/ggoferta-search
CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE=.secrets/ggoferta-core-client
```

O provider não é aceito no body público. `ECONOMY_PROVIDER`,
`STANDARD_PROVIDER` e `QUALITY_PROVIDER` permitem overrides por classe;
`FREE_ONLY` rejeita alvo pago e `MAX_RESULTS_LIMIT` é aplicado antes do
upstream. Uma lista vazia é resposta válida e não dispara retry/fallback.
`context7` é target gratuito certificado somente para o purpose
`technical_documentation`; seu corpus é focado em documentação de bibliotecas
e ele não é o default de Web Search geral. Enquanto `DEFAULT_PROVIDER` e os
overrides de classe estiverem vazios, busca geral permanece `not_configured`.
`duckduckgo-free` está bloqueado por anti-bot no ambiente local validado;
SearXNG foi certificado em DEV na 118G para `market_research`, mas requer
instância local com JSON habilitado e `providerSpecificData.baseUrl` no OmniRoute.
Para habilitar o alvo, configure também `CESAR_CORE_SEARCH_PROVIDER_HEALTH_URL`;
o probe de prontidão verifica essa dependência sem executar busca externa.
Sem serviço/configuração permanente, o default continua vazio. Ollama Search
continua sem credencial configurada. Ver ADR 0017.

`max_results` limita obrigatoriamente a saída. SearXNG pode adquirir mais
resultados internamente: OmniRoute corta a resposta e o Core garante o cap final.
Isso não é enforcement de aquisição externa nem um bug do provider.

`/v1/capabilities` distingue `search_general_web` de
`search_technical_documentation`. O status agregado `search` fica disponível
quando ao menos um target Search está configurado, sem afirmar que todos os
purposes possuem cobertura.

`/v1/capabilities` também informa `application_registry`,
`application_authentication` e `metrics`, sem listar credenciais nem expor o
consumidor reservado. `/ready` degrada se AI/Search estiver habilitado sem uma
credencial de aplicação legível ou sem a credencial OmniRoute específica da
capability. `/metrics` usa o formato de exposição Prometheus e somente labels
operacionais de baixa cardinalidade. A quota é uma fixed window de 60 segundos
por aplicação/capability, compartilhada em Redis e persistida em AOF. Restart do
Core não reinicia o saldo; réplicas devem usar o mesmo namespace, Redis e limites.
Excesso retorna `429 quota_exceeded` antes do upstream. Armazenamento inacessível
retorna `503 quota_store_unavailable`; configuração incompatível retorna
`503 quota_store_misconfigured`, sem consumo upstream nem fallback em memória.
`/ready` fica `degraded` com `reason` contendo esse código; saldo
esgotado não degrada readiness nem liveness. Ver [ADR 0018](docs/adr/0018-persistent-quota-recovery.md).

Reutilizar Redis da plataforma com volume persistente, `appendonly yes`,
`appendfsync always`, `no-appendfsync-on-rewrite no` e `maxmemory-policy noeviction`.
O Core verifica esses requisitos, não reconfigura o servidor. Configurar
`CESAR_CORE_SECURITY_QUOTA_REDIS_URL` sem segredo e, se autenticado,
`CESAR_CORE_SECURITY_QUOTA_REDIS_PASSWORD_FILE`; usar namespace estável exclusivo
por ambiente. O Redis original deste DEV não foi modificado: a prova usa uma
instância descartável da mesma imagem. Não habilitar gateways em outro ambiente
sem validar esses requisitos. A disponibilidade é fail-closed, não HA automática.

Para subir a API localmente:

```bash
uvicorn cesar_core.api.app:app --host 127.0.0.1 --port 8100
```

## Documentação

- `docs/adr/` -- decisões arquiteturais e suas atualizações de implementação.
- `contracts/` -- OpenAPI exportado da aplicação FastAPI.
- `deployment/` -- topologia pretendida de implantação (container-to-container,
  loopback-only); o exemplo ainda não é um deployment executável.

## Licença

Todos os direitos reservados. Ver [LICENSE](LICENSE). Componentes externos
mantêm suas próprias licenças. Esta distribuição não concede licença open source.
