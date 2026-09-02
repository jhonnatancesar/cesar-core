# César Core

Infraestrutura central multi-aplicação de IA, Web Search, políticas de uso e
identidade de aplicação consumidora. O repositório é independente do GG
Oferta e contém o transporte HTTP real de baixo nível para o OmniRoute.

## Estado atual

O projeto concluiu a fundação (**TASK-118A**), o transporte OmniRoute
(**TASK-118B**) e as primeiras fatias dos gateways centrais de AI
(**TASK-118C**) e Web Search (**TASK-118D**). Estão disponíveis:

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

Ainda não estão implementados a autenticação das aplicações consumidoras nem
o deployment de produção. Cada gateway aparece como `not_configured` enquanto
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
Não migra o Market Research do GG Oferta; essa integração pertence à 118G.

## Estrutura

```text
src/cesar_core/
  api/            aplicação FastAPI e rotas HTTP
  applications/   ApplicationId, ApplicationState, ApplicationContext, registry
  ai/             contrato, policy, manager e adapter OmniRoute de AI
  search/         contrato, policy, manager e adapter OmniRoute de Search
  omniroute/      client HTTP de baixo nível (health, chat completions, search)
  policy/         service_class, cost_policy, requirements
  security/       fronteira reservada para autenticação futura
  telemetry/      correlation ID (propagado) e request ID (gerado por requisição)
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

A configuração de exemplo está em `.env.example`. A chave do OmniRoute não
deve ser colocada no `.env`: `CESAR_CORE_OMNIROUTE_API_KEY_FILE` aponta para
um arquivo local fora do Git.

Para habilitar o endpoint AI, configure ao menos:

```env
CESAR_CORE_AI_ENABLED=true
CESAR_CORE_AI_DEFAULT_MODEL=<modelo disponível no OmniRoute>
CESAR_CORE_OMNIROUTE_API_KEY_FILE=.secrets/omniroute_api_key
```

O modelo não é aceito no body público: ele é escolhido pela policy interna.
`ECONOMY_MODEL`, `STANDARD_MODEL` e `QUALITY_MODEL` permitem overrides por
classe de serviço. `FREE_ONLY` rejeita um alvo marcado como pago.

Para habilitar o endpoint Search, configure ao menos:

```env
CESAR_CORE_SEARCH_ENABLED=true
CESAR_CORE_SEARCH_DEFAULT_PROVIDER=
CESAR_CORE_SEARCH_TECHNICAL_DOCUMENTATION_PROVIDER=context7
CESAR_CORE_OMNIROUTE_API_KEY_FILE=.secrets/omniroute_api_key
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
SearXNG e Ollama Search exigem configuração externa ainda inexistente.

`/v1/capabilities` distingue `search_general_web` de
`search_technical_documentation`. O status agregado `search` fica disponível
quando ao menos um target Search está configurado, sem afirmar que todos os
purposes possuem cobertura.

Para subir a API localmente:

```bash
uvicorn cesar_core.api.app:app --host 127.0.0.1 --port 8100
```

## Documentação

- `docs/adr/` -- decisões arquiteturais e suas atualizações de implementação.
- `contracts/` -- OpenAPI exportado da aplicação FastAPI.
- `deployment/` -- topologia pretendida de implantação (container-to-container,
  loopback-only); o exemplo ainda não é um deployment executável.
