# César Core

Infraestrutura central multi-aplicação de IA, Web Search, políticas de uso e
identidade de aplicação consumidora. Repositório independente do GG Oferta,
dono da integração real com o OmniRoute (que **não** é implementada nesta
fase de fundação).

## Escopo desta fase (TASK-118A)

Apenas a fundação: estrutura de projeto, identidade de aplicações
(`gg_oferta` = ACTIVE, `claudiao` = RESERVED), contratos neutros de AI/Search
(sem provider/model), modelos de política (`service_class`, `cost_policy`),
boundary do OmniRoute (sem chamadas reais) e os endpoints `/health`, `/ready`
e `/v1/capabilities`.

Não implementado nesta fase: chamadas reais ao OmniRoute, configuração de
Gemini/Groq/OpenRouter, o agente Claudião, deployment em produção.

## Estrutura

```text
src/cesar_core/
  api/            aplicação FastAPI e rotas HTTP
  applications/   ApplicationId, ApplicationState, ApplicationContext, registry
  ai/             contrato neutro de AI (sem provider)
  search/         contrato neutro de Web Search (sem provider)
  omniroute/      boundary/contrato do OmniRoute (sem chamadas reais)
  policy/         service_class, cost_policy, purpose, requirements
  security/       fronteira de segurança (fundação, sem lógica funcional)
  telemetry/      correlation/request ID
  health/         lógica de health/readiness/capabilities
  config/         settings do processo
```

## Desenvolvimento local

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

Para subir a API localmente:

```bash
uvicorn cesar_core.api.app:app --host 127.0.0.1 --port 8100
```

## Documentação

- `docs/adr/` -- decisões arquiteturais registradas nesta fase.
- `contracts/` -- OpenAPI exportado da aplicação FastAPI.
- `deployment/` -- topologia de implantação futura (container-to-container,
  loopback-only), ainda não aplicada em nenhum ambiente.
