# Segurança do Fetch/Enrichment — vazamento de dados na URL (FASE E.3)

Este documento é a fonte canônica de segurança para o vazamento de dados
(segredos/PII carregados na URL) no Central Web Fetch/Enrichment Gateway
(`POST /v1/fetch`). É complementar e independente do documento de SSRF
(`docs/architecture/gg-oferta-core.md`, seção "Segurança do Fetch/
Enrichment: SSRF encerrado para a topologia atual") — **as duas categorias
de risco nunca são misturadas no código nem na análise**:

- **SSRF** (`DEC-111`, GG Oferta): PRA ONDE a URL aponta na rede (loopback,
  RFC1918, metadata de nuvem etc.).
- **Vazamento de dados** (este documento): O QUE a URL carrega como dado
  (token, credencial, sessão, assinatura de nuvem) e para onde esse dado
  pode se propagar (logs, banco, prompt de IA).

## 1. Contexto e motivação

A URL de um resultado de busca é **input não confiável**: pode vir de
qualquer página indexada pela web aberta (Web Search via OmniRoute/
SearXNG), sem curadoria. Essa URL viaja, sem nenhuma transformação de
nenhuma camada intermediária, até um provider terceiro (hoje, Firecrawl
Cloud) e é usada para três finalidades distintas dentro do GG Oferta:

1. decidir **se** ela deve ser buscada (enriquecida);
2. o que fica registrado em `MarketPriceAssessment.evidence` (JSONB
   persistido) e usado como `title`/`domain` de `EvidenceItem`;
3. o que entra no prompt de `_interpret_evidence` (IA), via
   `market_evidence`/`history_evidence`.

Uma auditoria de segurança anterior a esta fase (read-only, sem alteração
de código) confirmou empiricamente, com um teste sintético ao vivo, que o
**OmniRoute loga a URL completa (query + fragment) em nível INFO, sempre**,
para toda chamada de `/v1/web/fetch` — sem essa hardening, um parâmetro de
URL como `?session_id=...`, `?access_token=...` ou uma URL assinada de
nuvem (`X-Amz-Signature=...`) chegaria: (a) aos logs do OmniRoute; (b)
potencialmente ao `evidence` persistido no Postgres do GG Oferta; (c)
potencialmente ao prompt enviado à IA de interpretação.

## 2. Modelo de decisão (mesmo em GG Oferta e César Core, por design)

Duas decisões distintas, **nunca combinadas na mesma função**:

- **"Devo buscar esta URL?"** — se ela carregar um parâmetro de ALTA
  CONFIANÇA (nome quase nunca aparece por acidente numa URL legítima de
  e-commerce) ou for uma URL assinada de nuvem conhecida, a resposta é
  **rejeitar o fetch inteiro**, nunca mascarar o valor e prosseguir.
  Mascarar produziria uma URL inválida (o provider não conseguiria buscar
  a página real) e esconderia o problema em vez de reportá-lo — decisão
  explícita do usuário/dono do produto, registrada aqui para não ser
  revertida por engano numa refatoração futura.
- **"Qual representação desta URL é segura para persistir/logar/
  promptar?"** — sempre sem `#fragment`, sempre sem os parâmetros de alta
  confiança/assinatura (removidos, nunca mascarados), preservando
  qualquer outro parâmetro legítimo de e-commerce (`id`, `sku`, `product`,
  `ref`, `page`, `category`, `code`, `key` — deliberadamente NUNCA
  tratados como sensíveis, para não recusar URL real de loja por falso
  positivo).

### 2.1 Lista de parâmetros de ALTA CONFIANÇA

Reimplementada de forma independente em cada repositório (GG Oferta e
César Core não compartilham pacote Python — são repos separados), como
segunda camada de defesa em profundidade: o Core não confia que todo
chamador (hoje só `gg_oferta`, mas a fronteira HTTP não garante isso para
sempre) já filtrou sua própria URL antes de chamar `/v1/fetch`.

```
access_token, refresh_token, oauth_token,
api_key, apikey, api-key,
authorization,
password, passwd,
session, session_id,
jwt
```

Mais URLs assinadas de provedores de nuvem conhecidas:

```
x-amz-signature, x-amz-credential, x-amz-security-token   (AWS SigV4)
x-goog-signature, x-goog-credential                        (Google Cloud)
sig + sv (combinados)                                       (Azure SAS)
```

Azure SAS não tem um nome de parâmetro único — é caracterizado pela
combinação de `sig` (assinatura) com `sv` (service version); `sig` ou `sv`
isolados **não** disparam a detecção (evita falso positivo com uso
genérico desses nomes em outra loja).

**Deliberadamente fora da lista** (para nunca recusar URL legítima de
e-commerce por falso positivo): `id`, `sku`, `product`, `ref`, `page`,
`category`, `code`, `key`.

## 3. O que foi implementado

### 3.1 GG Oferta (`C:\AIShoppingAgent\AIShoppingAgent`)

Módulo central e único responsável por esta política:
[`backend/app/search/url_safety.py`](../../../AIShoppingAgent/AIShoppingAgent/backend/app/search/url_safety.py)
(caminho relativo aproximado — repositório separado).

| Função | Responsabilidade |
|---|---|
| `has_sensitive_query_data(url)` | `True` se a query carregar parâmetro de alta confiança ou URL assinada de nuvem conhecida. |
| `is_safe_to_fetch(url)` | Decisão SE a URL deve ser enviada ao César Core. Só considera dado sensível na URL — SSRF é responsabilidade separada do Core. |
| `url_for_fetch_request(url)` | URL efetivamente enviada ao Core: idêntica à original, exceto pelo `#fragment` (removido). Só deve ser chamada depois de `is_safe_to_fetch(url)` confirmar `True` — não decide SE buscar, só normaliza o que é enviado. |
| `safe_url_for_evidence(url)` | Representação seguríssima para persistência (`evidence`) e prompt de IA: sem fragment, sem parâmetros de alta confiança/assinatura, demais parâmetros preservados. |
| `redact_sensitive_query_values(text)` | Redige `chave=valor` de alta confiança dentro de texto livre (ex.: mensagem de exceção), sem assumir que o texto é uma URL bem formada. Retorna `RedactionResult(text, redacted)`. |

Integração em [`backend/app/market_research/service.py`](../../../AIShoppingAgent/AIShoppingAgent/backend/app/market_research/service.py),
função `_search_with_enrichment`:

```python
for url in candidate_urls:
    if not is_safe_to_fetch(url):
        observe_scrape(outcome="blocked", correlation_id=response.correlation_id)
        continue
    try:
        page = await enrichment.scrape_basic(url_for_fetch_request(url))
    except CesarCoreFetchError:
        ...
    safe_url = safe_url_for_evidence(url)
    title = page.title or safe_url          # antes: `page.title or url` (BUG corrigido)
    ...
```

**Bug corrigido nesta fase:** o fallback de título usava a URL ORIGINAL
(potencialmente insegura) quando o provider não retornava título — isso
vazaria o segredo para o campo `title`, que também é persistido/
promptado. Corrigido para usar `safe_url` (já sanitizada).

Também em `mark_assessment_failed`: `error` é redigido
(`redact_sensitive_query_values(error).text`) antes de ser truncado e
persistido em `last_error`.

Telemetria: `backend/app/search/telemetry.py` define
`SCRAPES = Counter("aishopping_scrape_enrichment_total", ..., ("outcome",))`
com label genérico (sem enum fixo) — o novo valor `outcome="blocked"` é
seguro sem qualquer alteração nesse arquivo.

**Testes:** `tests/test_url_safety.py` (35 casos: detecção de cada chave
sensível, Azure SAS por combinação, parâmetros comuns de e-commerce NUNCA
sinalizados, fragment sempre removido em `safe_url_for_evidence`/
`url_for_fetch_request`, redação em texto livre com múltiplas ocorrências).

### 3.2 César Core (`C:\cesar-core`)

Segunda camada independente, em
[`src/cesar_core/fetch/contracts.py`](../../src/cesar_core/fetch/contracts.py):

| Função | Responsabilidade |
|---|---|
| `reject_sensitive_query_target(url)` | Mesma lista de chaves de alta confiança do GG, reimplementada. Levanta `ValueError` — rejeita a URL inteira, nunca mascara. **Deliberadamente separada de `reject_ssrf_target`** (SSRF é sobre PRA ONDE; isto é sobre O QUE). |
| `strip_url_fragment(url)` | Remove `#fragment`, se houver. Puramente sintático (sem I/O). |

Ambas chamadas dentro do `field_validator` de `FetchRequestPayload.url`
(ao contrário de `reject_ssrf_target`, que faz resolução DNS — I/O de
rede — e por isso fica fora do validador, chamada explicitamente pela
rota `POST /v1/fetch`). Isso significa que **qualquer** caminho de
construção de `FetchRequestPayload`/`FetchRequest` (não só a rota HTTP)
já aplica as duas defesas automaticamente.

`FetchRequestPayload` também ganhou `model_config = ConfigDict(extra=
"forbid")` — um campo desconhecido no corpo (ex.: um futuro `provider`
adicionado por engano) é rejeitado com HTTP 422 antes de qualquer chamada
ao `FetchManager`/upstream. Isso é consistente com o padrão já usado em
`AIRequestPayload` (`src/cesar_core/ai/contracts.py`); `SearchRequestPayload`
ainda não tem `extra="forbid"` — gap pré-existente, fora do escopo desta
fase (não tocado).

**Efeito no contrato HTTP observável:**

- URL malformada (não http(s) absoluto) → **422** (comportamento
  pré-existente, mesmo validador).
- URL com parâmetro sensível → **422** (novo, mesmo validador — falha de
  validação de payload, não é uma decisão de política de negócio).
- URL apontando para alvo interno/privado (SSRF) → **400**
  `fetch_target_rejected` (comportamento pré-existente, `DEC-111`,
  chamada explícita na rota, fora do validador por causa do DNS).

**Testes:** `tests/test_fetch_data_leakage_guard.py` (30 casos, mesma
cobertura do lado GG, mais os dois guards em conjunto via
`FetchRequestPayload` e o teste de `extra="forbid"`) + 2 testes de rota
real em `tests/test_api_routes.py`
(`test_fetch_rejects_a_sensitive_query_parameter_before_reaching_the_manager`,
`test_fetch_rejects_an_unknown_payload_field`).

### 3.3 OmniRoute — nível de log (mitigação de log, não de código)

`compose.yaml`, serviço `omniroute`:

```yaml
environment:
  APP_LOG_LEVEL: warn
```

Mecanismo **oficial e documentado** do próprio OmniRoute (`debug|info|
warn|error`, default `info`) — nenhum fork/patch do binário oficial
(`diegosouzapw/omniroute@sha256:...`, nunca reconstruído). Reduz o log de
acesso que incluía a URL completa (query + fragment) de cada
`/v1/web/fetch` em nível INFO — achado confirmado empiricamente na
auditoria anterior a esta fase. Isso é defesa em profundidade: mesmo que
uma URL sensível escapasse (por algum caminho ainda não coberto) dos dois
guards acima, ela não seria mais logada rotineiramente pelo OmniRoute.

**Risco residual aceito:** nível `warn` ainda pode registrar uma URL em
erros/avisos produzidos pelo provider terceiro. Os guards independentes do
GG e do Core impedem que parâmetros de alta confiança cheguem ao upstream,
mas isso não substitui uma futura auditoria de cada mensagem de erro do
OmniRoute/provider.

## 4. Fechamento das pendências

### 4.1 Auditoria integral dos bancos DEV e PROD

Auditoria exclusivamente `SELECT`, sem exibir URL ou valor de parâmetro:

- DEV: `market_price_assessments` vazio (0 registros), nenhum indicador.
- PROD: runtime confirmado no Windows Server autoritativo, banco
  `aishoppingagent`, 5/5 assessments e 50 URLs de `evidence` auditados
  recursivamente, além de `historical_low_source` e `last_error`.
- Resultado PROD: 0 fragmentos, 0 parâmetros de alta confiança, 0 URLs
  assinadas, 0 famílias sensíveis, 0 `last_error` suspeitos e 0 possíveis
  segredos reais.

Os 5 registros são snapshots consolidados; o mesmo banco continha 31.795
`price_observations`, confirmando que a auditoria não confundiu a tabela-alvo
com a população total do banco. Nenhum dado/schema foi alterado.

### 4.2 Minimização do conteúdo enviado à IA

Antes, `_interpret_evidence` enviava `description`/markdown sem limite. Cada
uma das duas buscas pede até 6 resultados e o enrichment pode acrescentar até
3 itens; no pior arranjo, 12 descrições sem limite podiam entrar no prompt.

Agora todos os itens e URLs continuam presentes, mas o texto livre é limitado
deterministicamente antes de construir a `AIRequest`: título em 500 caracteres
e descrição em 2.000. Conteúdo maior preserva começo e fim, separados pelo
marcador `[conteúdo intermediário omitido]`. Assim permanecem produto, loja,
preço, condição, promoção e contexto normalmente posicionados nos extremos da
página, sem enviar dezenas de milhares de caracteres. A validação de identidade
continua usando o conteúdo original; a redução afeta somente o prompt.

### 4.3 Integração PostgreSQL focada

`py -3 scripts/run_integration_tests.py tests/integration/test_market_research.py`
subiu PostgreSQL 18.4 descartável, migrou até `20260901_0002` e aprovou 13/13
testes. A cobertura inclui URL segura persistida, fragment/token ausentes,
URL sensível sem upstream, `last_error` redigido, minimização do prompt,
Market Research preservado e enrichment fail-soft. Recursos descartáveis foram
limpos pelo runner.

### 4.4 Revisão final dos findings de segurança

- SSRF inicial: válido e corrigido pelo guard do Core antes do upstream.
- Redirect/DNS rebinding: válido como risco residual do provider terceiro;
  não é alcançável diretamente no Core/OmniRoute da topologia Firecrawl Cloud
  atual e permanece registrado com gatilho de reabertura.
- URL sensível em logs/evidence/prompt: válido e corrigido pelos guards,
  sanitização, redação e nível `warn` do OmniRoute.
- Markdown ilimitado no prompt: válido e corrigido pela minimização acima.
- `extra` desconhecido no Fetch: válido e corrigido com `extra="forbid"`.
- Parâmetros genéricos de e-commerce (`id`, `sku`, `ref`, `code`, `key`):
  falso positivo quando tratados isoladamente como segredo; preservados por
  decisão explícita para evitar quebra de URLs legítimas.

## 5. Como verificar esta hardening (comandos de referência)

GG Oferta:

```bash
python -m pytest tests/test_url_safety.py -q
python -m pytest tests/test_web_search_manager.py tests/test_cesar_core_fetch_provider.py -q
```

César Core:

```bash
python -m pytest tests/test_fetch_data_leakage_guard.py tests/test_fetch_ssrf_guard.py -q
python -m pytest tests/test_api_routes.py -k fetch -q
python -m pytest tests/test_openapi_contract.py -q
```

## 6. Estado no momento deste documento

Código e testes implementados e verdes nos dois repositórios (ver seção
3). **Nenhum commit/push foi feito em nenhum dos dois repositórios** —
todo o trabalho descrito aqui está no working tree local. `contracts/
openapi.json` (César Core) foi regenerado (`python scripts/
export_openapi.py`) para refletir `extra="forbid"` no schema de
`FetchRequestPayload` — esse arquivo já estava desatualizado desde antes
desta fase (faltava o endpoint `/v1/fetch` inteiro), sem relação com esta
mudança específica.

## 7. Fontes complementares

- SSRF (categoria de risco irmã, já encerrada): `docs/architecture/
  gg-oferta-core.md`, seção "Segurança do Fetch/Enrichment: SSRF
  encerrado para a topologia atual"; GG Oferta `DEC-111`.
- Arquitetura geral da integração: `docs/architecture/gg-oferta-core.md`.
- GG Oferta: `docs/internal/decision-log.md`, `DEC-112` (aponta para este
  documento).
