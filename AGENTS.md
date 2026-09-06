# Instruções para agentes

## Integração GG Oferta ↔ César Core

Antes de qualquer alteração envolvendo AI, Search, providers, fallback,
grounding, César Core, OmniRoute, Firecrawl ou Docker/configuração GG ↔ Core,
leia integralmente `docs/architecture/gg-oferta-core.md` e as ADRs ali
referenciadas.

Preserve a arquitetura `GG Oferta → César Core → OmniRoute → providers`.
Um target lógico do Core não substitui uma conexão real no OmniRoute. Search e
Firecrawl Scrape são capacidades diferentes. Não transforme uma topologia
temporária de DEV em arquitetura oficial. GG Oferta e seu worker nativo nunca
devem depender diretamente de um provider externo (Gemini, Groq, OpenRouter,
Firecrawl, SearXNG ou futuros) para capacidades cobertas por essa arquitetura
— a dependência é sempre o César Core; providers concretos ficam abaixo dele.

## Testes e o `.env` operacional

Testes do César Core devem neutralizar a configuração operacional (`.env`) e
nunca depender do cwd de quem chamou o `pytest` ou do `.env` de DEV real
(toda classe `BaseSettings` usa `env_file=".env"`, resolvido pelo cwd —
`tests/conftest.py` já faz isso via fixture autouse, ver
`tests/test_settings_env_isolation.py`). Nunca remova esse isolamento nem
crie uma classe de configuração nova sem verificar que ele continua
cobrindo-a.
