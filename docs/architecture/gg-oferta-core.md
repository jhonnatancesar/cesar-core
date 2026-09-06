# Arquitetura GG Oferta ↔ César Core

Este documento é a fonte canônica da integração entre o GG Oferta e o
César Core. Antes de alterar AI, Search, providers, fallback, grounding,
OmniRoute, Firecrawl ou a topologia/configuração entre os projetos, leia este
documento e as ADRs das capacidades envolvidas.

## Arquitetura obrigatória

```text
GG Oferta
  ├─ AIProviderManager
  └─ WebSearchManager
          │
          ▼
      César Core
      ├─ Application Identity
      ├─ Capability Authorization e Policy
      ├─ AI Gateway e Search Gateway
      ├─ Usage e Quota
      ├─ Tracing
      └─ Health
          │
          ▼
       OmniRoute
      ├─ AI providers
      └─ Search providers
```

- O GG Oferta decide intenção e regras de negócio. Ele não chama o
  OmniRoute diretamente.
- O César Core autentica a aplicação, autoriza a capability, aplica policy e
  quota antes do upstream, registra usage/tracing e normaliza AI/Search.
- O OmniRoute possui as conexões reais e executa/roteia providers concretos.
  Um target lógico configurado no Core não cria uma conexão no OmniRoute.
- Web Search encontra URLs. Firecrawl `/v2/scrape` extrai conteúdo de URLs já
  conhecidas e permanece uma capacidade de enriquecimento separada.

## Decisão de topologia

A decisão estrutural foi registrada no GG Oferta em
`docs/internal/decision-log.md`, DEC-118, item 8:

- PROD V1: mesmo Windows Server físico;
- deployments independentes em `C:\App\AIShoppingAgent`,
  `C:\App\cesar-core` e `C:\App\omniroute`;
- repositório, configuração, secrets e lifecycle próprios;
- rede Docker externa conceitual `cesar-platform` entre deployments;
- César Core também acessível pelo host local, porque o
  `collection_worker` roda nativamente no Windows;
- nenhuma exposição pública do Core ou do OmniRoute.

Essa decisão não autoriza `0.0.0.0`, endpoint público, HTTPS improvisado ou
uma composição única dos três repositórios.

## Topologia da primeira prova DEV

A TASK-118F e o handoff `docs/operations/cesar-core-v1-dev-handoff.md` do GG
Oferta validaram uma topologia mais estreita para a primeira prova:

```text
processo GG Oferta nativo no Windows
  → http://127.0.0.1:8100
  → César Core DEV
  → OmniRoute 3.8.50
  → provider real
```

Esse loopback é a topologia operacional da FASE 0/A em DEV, não substitui a
decisão estrutural de PROD e não torna `127.0.0.1` válido de dentro de um
container. O Compose atual do GG Oferta ainda não transporta configuração ou
secret do César Core. Conectividade container → Core deve obedecer à rede
externa decidida e ser validada numa fase própria; não usar
`host.docker.internal` como arquitetura substituta.

## Configuração e credenciais

O consumidor usa uma credencial exclusiva GG Oferta → César Core por arquivo.
O Core usa credenciais distintas para AI e Search ao chamar o OmniRoute. Nenhum
desses valores pode ser reutilizado entre fronteiras.

Para uma capability ficar operacional, quatro condições são independentes:

1. a flag da capability está habilitada no GG Oferta;
2. a mesma capability está habilitada e possui target lógico no Core;
3. o OmniRoute possui conexão/provider real compatível com o target;
4. `/ready` confirma autenticação, quota e upstreams necessários.

Para Search geral, o target certificado é `searxng-search`, cuja conexão real
no OmniRoute aponta para o endpoint interno `/search` do SearXNG. `context7`
continua restrito a documentação técnica.

## Estado da FASE E.1 — AI, Search e enrichment concluídos

AI normal e AI com grounding de `USER`, `ADMIN` e `DEV` usam exclusivamente
`AIProviderManager → CesarCoreAIProviderManager → César Core → OmniRoute`. A
factory de AI não é mais opt-in: `cesar_core_ai_enabled` e as demais flags
`AISHOPPING_CESAR_CORE_*_ENABLED` foram removidas do GG Oferta (não existem
mais no `Settings`); credencial/config ausente fecha o fluxo diretamente, sem
flag para desviar. A configuração antiga de disaster fallback também foi
removida. Indisponibilidade, timeout ou erro HTTP do Core são propagados de
modo fail-closed, sem cascata direta para Gemini/Groq/OpenRouter.

`require_search_grounding=True` viaja no contrato neutro GG → Core. O Core pede
Web Search ao OmniRoute, exige evidência estruturada, conclui a geração no mesmo
gateway e normaliza fontes e usage agregado. Falha de ferramenta, ausência de
evidência ou falha na conclusão fecha o fluxo sem provider direto.

Os adapters, factories, configurações e dependência exclusivos de
Gemini/Groq/OpenRouter diretos foram removidos do GG Oferta. Nenhuma factory
pública instancia provider AI concreto fora do Core.

Search normal usa exclusivamente
`WebSearchManager → CesarCoreSearchProvider → César Core → OmniRoute`.
Deixar a credencial do Core ausente fecha a factory. Firecrawl `/v2/search`,
seu parser e seu adapter foram removidos.

**Enrichment agora também vive atrás do Core (FASE E.1, fecha a pendência
registrada na FASE E).** O César Core ganhou o Central Web Fetch/Enrichment
Gateway: contrato neutro `POST /v1/fetch` (`src/cesar_core/fetch/`, mesmo
padrão de Identity/Policy/Capability/Quota/Usage/Tracing já aplicado a
AI/Search), adapter `OmniRouteFetchProvider` traduzindo para o contrato real
do OmniRoute (`POST /v1/web/fetch`, que já reconhecia Firecrawl como um dos
seus providers — achado do `DEC-107`, repositório GG Oferta). O GG Oferta
(`Market Research`, worker nativo) trocou `FirecrawlScrapeProvider` por
`CesarCoreFetchProvider` (`app/search/cesar_core_fetch.py`) e não guarda mais
nenhuma credencial, endpoint ou nome de provider de enriquecimento — reusa a
mesma credencial de aplicação já usada por AI/Search. O cliente Firecrawl
direto (`app/search/firecrawl.py`) e os secrets/env vars exclusivos dele
(`AISHOPPING_FIRECRAWL_API_KEY(_FILE)`) foram removidos do GG Oferta depois
de comprovado que não havia mais consumidor.

Capability `fetch` no Control Plane do Core: nova migration
(`0002_add_fetch_capability.sql`) estende os CHECKs de
`application_capabilities`/`quota_policies`/`usage_rollups`; `gg_oferta` já
nasce com a capability em bootstraps novos, e o Control Plane administrativo
aceita `fetch` em `capabilities`/`quotas` (mesmo fluxo de API Admin já usado
para `ai`/`search`, ADR 0018). Conteúdo vazio/bloqueado da origem específica
é normalizado como `fetched=false` (sucesso de negócio, nunca exceção) — a
mesma semântica que o cliente Firecrawl direto já tinha.

Com isso, nenhuma das três capacidades (AI, Search, enrichment) depende
diretamente de um provider externo no GG Oferta ou no seu worker nativo — a
dependência é sempre o César Core; Firecrawl (e os demais providers de
`/v1/web/fetch`: Jina Reader, Tavily, TinyFish) ficam abaixo do OmniRoute.

**FASE E.1 concluída integralmente, incluindo E2E real.** Próxima fase:
FASE F, fechamento operacional/documental do escopo completo (AI, grounding,
Search, enrichment) — sem E2E pendente.

## Segurança do Fetch/Enrichment: SSRF encerrado para a topologia atual

`POST /v1/fetch` valida a URL de entrada (`reject_ssrf_target`, GG Oferta
`DEC-111`): bloqueia loopback/RFC1918/link-local/reservado/metadata de
nuvem, credenciais embutidas na URL e portas fora de 80/443 -- defesa em
profundidade, antes de qualquer chamada upstream. Auditoria do código-fonte
real do OmniRoute confirmou que nenhum dos 5 providers de `/v1/web/fetch`
(firecrawl, jina-reader, tavily, tinyfish, context7) conecta diretamente no
host da URL alvo -- cada um só chama a API fixa do próprio provider,
passando a URL como dado. Quem de fato executa o acesso ao alvo (e um
eventual redirect dele) é o provider terceiro configurado -- hoje
exclusivamente **Firecrawl Cloud**, cujo advisory `GHSA-vjp8-2wgg-p734`
declara a correção do SSRF por redirect nesse serviço (Cloud, 27/12/2024).
A ressalva do próprio Firecrawl sobre instalações self-hosted/OSS não se
aplica a esta topologia. **Se o provider padrão migrar pra Firecrawl
self-hosted (ou outro), reabrir esta análise** e avaliar proxy/egress
filtering. Nem o Core nem o OmniRoute garantem proteção contra DNS
rebinding no provider terceiro -- essa é uma trust boundary externa a
este repositório.

Validação desta rodada: Core — 77 testes novos/ajustados (contrato, policy,
manager, adapter OmniRoute, fronteira de domínio, capabilities/health,
OpenAPI) passando a partir de um ambiente limpo (o `.env` real de DEV deste
repositório, com segredos de outras capabilities, causa um bug de
`pydantic-settings` — `extra="forbid"` rejeitando chaves de outros prefixos —
que já existia antes desta mudança e não foi corrigido aqui; ver runbook).
GG Oferta — suíte completa não-integração: 1766 passed, mesmas 6 falhas
pré-existentes sem relação (contrato de schema de `products`/`users` e
sessão de autenticação).

**E2E real executado e aprovado** (autorização explícita do usuário, mesma
rodada): stack Docker DEV do César Core rebuildado (`cesar-core:local`) e
recriado; Redis/OmniRoute/SearXNG preservados sem reset de volume. Prova
direta `POST /v1/web/fetch` no OmniRoute e prova completa
`CesarCoreFetchProvider (GG) → Core /v1/fetch → OmniRoute /v1/web/fetch →
Firecrawl` retornaram conteúdo real (ex.: página da Wikipedia sobre a
RTX 50 series, ~20 KB de markdown). Teste focado real de
`app.market_research.service._search_with_enrichment` (GG) contra Search
(SearXNG) e enrichment reais confirmou o comportamento de negócio inalterado:
enrichment só roda quando a busca sozinha não basta, teto de 3 URLs por
chamada, nenhuma URL inventada.

**Achado operacional importante:** credenciais OmniRoute são autorizadas por
categoria de endpoint (`allowedEndpoints`) POR CHAVE, no próprio painel
administrativo do OmniRoute — uma chave sem essa lista aceita qualquer
endpoint (compatibilidade retroativa), mas uma vez restringida só aceita as
categorias explicitamente listadas. As chaves `ggoferta-ai`/`ggoferta-search`
já existentes tinham escopo restrito às suas próprias categorias; por isso
a instância deste projeto exige uma credencial OmniRoute **dedicada e
minimamente escopada por capability** (`ggoferta-fetch`, escopo único
`web-fetch`) — nunca ampliar o escopo de uma chave existente nem reutilizar
seu valor para uma capability diferente. A instância OmniRoute DEV também
precisou de uma conexão de provider própria para Firecrawl (chave real do
Firecrawl, já provisionada anteriormente para o GG, agora registrada no
OmniRoute — o único lugar onde essa credencial deve viver a partir de agora).

## Segurança do Fetch/Enrichment: vazamento de dados na URL (FASE E.3)

Categoria de risco separada de SSRF (seção acima): não é sobre PRA ONDE a
URL aponta, é sobre O QUE ela carrega como dado. Uma URL de resultado de
busca com parâmetro de alta confiança (token, credencial, sessão,
assinatura AWS/GCS/Azure SAS) é sempre **rejeitada** para fetch (nunca
mascarada) tanto no GG Oferta (`app/search/url_safety.py`) quanto,
independentemente, no César Core (`reject_sensitive_query_target` em
`src/cesar_core/fetch/contracts.py`, junto de `strip_url_fragment` e
`FetchRequestPayload` com `extra="forbid"`). `compose.yaml` do OmniRoute
recebeu `APP_LOG_LEVEL: warn` (mecanismo oficial) para reduzir o log de
acesso que expunha a URL completa em INFO. `_interpret_evidence` limita o
texto livre enviado à IA (500 caracteres de título e 2.000 de descrição,
preservando começo/fim), sem reduzir fontes nem mudar a validação de identidade.
As auditorias integrais de DEV e PROD não encontraram segredo persistido; os
13/13 testes PostgreSQL focados passaram. Documento canônico:
`docs/security/fetch-data-leakage-hardening.md`. **FASE E.3 concluída.**

## Fontes complementares

- Core: ADRs 0003, 0006, 0014, 0015, 0017 e 0018.
- GG Oferta: TASK-118, TASK-118F, TASK-118G, TASK-118H, ADR-016 e ADR-017.
- Operação Core: `docs/deployment/docker.md`.
- Primeira prova GG: `docs/operations/cesar-core-v1-dev-handoff.md` no GG
  Oferta.
