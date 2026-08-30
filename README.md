# César Core

Infraestrutura central multi-aplicação de IA, Web Search, políticas de uso e
identidade de aplicação consumidora. Repositório independente do GG Oferta,
dono da integração real com o OmniRoute (que **não** é implementada nesta
fase de fundação).

## Escopo

**TASK-118A** (fundação): estrutura de projeto, identidade de aplicações
(`gg_oferta` = ACTIVE, `claudiao` = RESERVED), `ApplicationContext` completo
(application/service/purpose/request_id/correlation_id), contratos neutros
de AI/Search com boundary de provider próprio para cada um (sem chamadas
reais), modelos de política (`service_class`, `cost_policy`) e os endpoints
`/health`, `/ready` e `/v1/capabilities` -- semântica exata em ADR 0008.

**TASK-118B** (transporte OmniRoute): `omniroute/client` real -- config,
autenticação, timeout, erros, health, serialização/desserialização,
correlation -- validado por testes de contrato reais contra uma instância
do OmniRoute rodando localmente numa versão pinada (ver ADR 0011). Ainda
sem regras de negócio, sem adapters de AI/Search, sem configuração de
Gemini/Groq/OpenRouter, sem o agente Claudião, sem deployment em produção.

## Estrutura

```text
src/cesar_core/
  api/            aplicação FastAPI e rotas HTTP
  applications/   ApplicationId, ApplicationState, ApplicationContext, registry
  ai/             contrato + provider boundary próprios de AI (sem provider concreto)
  search/         contrato + provider boundary próprios de Search (sem provider concreto)
  omniroute/      client HTTP de baixo nível (config, auth, erros, health, timeout)
  policy/         service_class, cost_policy, requirements
  security/       fronteira de segurança (fundação, sem lógica funcional)
  telemetry/      correlation ID (propagado) e request ID (gerado por requisição)
  health/         lógica de health/readiness/capabilities
  config/         settings do processo
```

`ai/` e `search/` nunca compartilham uma interface de provider: cada um
tem a sua (`ai/provider.py`, `search/provider.py`). Um adapter real para
o OmniRoute chega depois em `ai/providers/omniroute.py` e
`search/providers/omniroute.py` -- ver ADR 0006.

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

Para subir a API localmente:

```bash
uvicorn cesar_core.api.app:app --host 127.0.0.1 --port 8100
```

## Documentação

- `docs/adr/` -- decisões arquiteturais registradas nesta fase.
- `contracts/` -- OpenAPI exportado da aplicação FastAPI.
- `deployment/` -- topologia de implantação futura (container-to-container,
  loopback-only), ainda não aplicada em nenhum ambiente.
