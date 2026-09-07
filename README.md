# César Core

Gateway central privado de AI e Web Search, com identidade de aplicação,
policies de execução, quotas persistentes e observabilidade. Distribuição
**1.2.0**, com todos os direitos reservados. A sequência TASK-118 está concluída;
publicar esta release não implanta nem modifica o GG Oferta em PROD.

## Arquitetura

```text
Consumers (por exemplo, GG Oferta)
    ↓ Bearer próprio da aplicação
César Core
    ├── Redis — quota compartilhada/durável
    └── OmniRoute — gateway upstream
          ├── AI providers / target configurado
          └── SearXNG — General Web Search
```

Uma codebase e duas execuções oficiais: **Docker recomendado para operação**;
Python/venv suportado para desenvolvimento e debug. O container instala o mesmo
pacote de `src/cesar_core`, sem fork ou implementação paralela. São quatro
imagens separadas; o Core não contém nem modifica o OmniRoute.

## Recursos e limites

- Bearer obrigatório em AI/Search; identidade derivada da credencial, não do body.
- Registry persistente: `gg_oferta=ACTIVE`; `claudiao=RESERVED` e protegido.
- Autorização por capability e policies por aplicação/purpose/service class.
- Classes economy/standard/quality; `FREE_ONLY` bloqueia targets declarados pagos.
- Quota AI/Search pré-upstream, atômica, compartilhada e sem fallback em memória.
- Readiness autenticada, métricas Prometheus, request/correlation/upstream IDs.
- AI: exatamente um de `prompt` ou `messages`; roles system/user/assistant e
  ordem preservadas até o OmniRoute. Sem streaming/tools/multimodal nesta versão.
- `max_tokens` exige capability de enforcement certificada para target fixo;
  validação fail-closed da resposta permanece. Alias dinâmico não pode declarar
  essa garantia. Resposta sem texto válido não é aceita como geração bem-sucedida.
- Search: títulos, URLs, snippets, usage, provider, cache e erros normalizados.
  Cache vem do OmniRoute; não é cache persistido no Core.
- Lista vazia é sucesso. Fallback segue policy/provider, não “resultado ruim”.
  O Core não implementa Firecrawl scrape nem estratégia de Market Research.
- `context7` é documentação técnica (`technical_documentation`), não Web Search
  geral. SearXNG é o target geral certificado para `market_research`.
- Control Plane em `/admin`: aplicações, credenciais, quotas, uso, rotas e saúde.
  Novas aplicações nascem `DISABLED`; não há exclusão pela interface.

## Control Plane

A interface administrativa React é servida pelo próprio Core em
`http://127.0.0.1:8100/admin`. Ela oferece exatamente seis áreas: visão geral,
aplicações, chaves de API, uso/quotas, rotas e saúde. Há temas claro e escuro;
no primeiro acesso o tema do sistema é respeitado e a escolha posterior fica
somente no `localStorage` do navegador.

O painel fica indisponível (`503`) até senha Argon2id, pepper de credenciais e
origem permitida estarem configurados. Gere o hash sem ecoar a senha:

```sh
cesar-core-admin-hash-password > .secrets/admin-password-hash
```

Crie o pepper com ao menos 32 bytes aleatórios e use o override dedicado:

```sh
docker compose -f compose.yaml -f deploy/compose.control-plane.yaml up -d
```

Credenciais novas usam `cc_<id>.<secret>`; somente HMAC com pepper é persistido,
e o segredo é exibido uma vez. A credencial legada do GG Oferta permanece
compatível e somente leitura. Sessões usam cookie opaco HttpOnly/SameSite=Strict,
expiração absoluta e por inatividade, CSRF e validação Origin/Host. Em HTTPS,
`CESAR_CORE_ADMIN_COOKIE_SECURE` deve permanecer `true`; `false` é exceção de
loopback DEV.

Quota efetiva por aplicação (`quota_policies`) é decidida aqui, não no lado
do consumidor — ver [ADR 0018](docs/adr/0018-persistent-quota-recovery.md).
Instalação e funcionalidade da integração vistas do lado de um consumidor
real (GG Oferta): `docs/installation/cesar-core.md` e
`docs/architecture/cesar-core-integration.md` no repositório
[jhonnatancesar/AIShoppingAgent](https://github.com/jhonnatancesar/AIShoppingAgent)
(privado, separado deste). Para subir GG Oferta + este Core/OmniRoute +
o Coupon Worker juntos, do zero, na ordem certa:
`docs/installation/integrated-setup.md` no mesmo repositório. Para
executar o deploy em PROD dos três componentes juntos (repositórios,
migrations, provisionamento OmniRoute, ordem, gate Gemini):
`docs/operations/prod-deployment-handoff.md`, também no repositório
`AIShoppingAgent`. Arquitetura canônica desta integração (topologia,
policy de providers AI, validação real): `docs/architecture/gg-oferta-core.md`
neste repositório.
O procedimento completo para colocar os dois projetos em funcionamento em DEV,
incluindo configuração dos dois lados e smoke tests, está em
[Arquitetura canônica GG Oferta ↔ César Core](docs/architecture/gg-oferta-core.md)
e [integração em DEV](docs/integration/gg-oferta-dev.md).

## Execução Docker / Compose (recomendada)

Pré-requisitos: Docker Engine/Desktop com Linux containers, Compose v2 e
linux/amd64; acesso autorizado ao repositório e ao package **privado** no GHCR.
Não é necessário Python nem build no servidor.

1. Obtenha `compose.yaml`, `deploy/` e `.env.example` da tag desejada.
2. Copie `.env.example` para `.env`; ele contém apenas configuração e caminhos.
3. Crie os arquivos locais de credencial descritos em “Secrets”. Não os versione.
4. Autentique Docker no GHCR com credencial autorizada de leitura de packages.
5. Prepare o OmniRoute pela interface oficial conforme o
   [primeiro boot](docs/deployment/docker.md). Ative gateways só após configurar
   suas chaves/targets.
6. Execute:

```sh
docker compose pull
docker compose up -d
docker compose ps
curl http://127.0.0.1:8100/health
curl http://127.0.0.1:8100/ready
```

O Compose usa `ghcr.io/jhonnatancesar/cesar-core:1.2.0`, não `build:`.
Para deploy reproduzível, defina `CESAR_CORE_IMAGE` com o digest publicado pelo
workflow: `ghcr.io/jhonnatancesar/cesar-core@sha256:<digest>`.
A rede backend é interna; OmniRoute/SearXNG usam a rede egress para providers.
Core também usa uma bridge ingress para a publicação da porta no host; essa
bridge não é uma garantia de bloqueio de saída do Core.
Somente Core é publicado, em `127.0.0.1:8100`. Redis/SearXNG não têm porta no host.
Não usar localhost para comunicação entre containers: os nomes são
`redis`, `omniroute` e `searxng`.

Para rodar apenas o container Core, conecte-o à rede das dependências, passe as
mesmas variáveis de runtime e monte os três arquivos de credencial em read-only.
O Compose é o caminho suportado mais simples; não embutir credenciais na imagem.
O acesso remoto exige proxy/TLS e decisão de rede própria, não incluídos neste
rollout. Ver [operação Docker](docs/deployment/docker.md).

## Execução nativa (DEV)

Use Python oficial 3.12+; a baseline validada usa 3.14.6.

```sh
python -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell, em vez da linha anterior:
# .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m uvicorn cesar_core.api.app:app --host 127.0.0.1 --port 8100
```

Configure dependências reais acessíveis ao host e os mesmos arquivos `*_FILE`.
Não aponte o host para nomes DNS exclusivos da rede Docker.
O modo nativo usa o mesmo registry, auth, policies, Redis e adapters.

## Configuração

O arquivo [.env.example](.env.example) lista as opções nativas. O Compose mapeia
explicitamente a configuração operacional abaixo; não lê secrets do build.

| Variável | Papel |
|---|---|
| `CESAR_CORE_IMAGE` | Tag ou digest da imagem; padrão GHCR 1.2.0 |
| `CESAR_CORE_PUBLISHED_PORT` | Porta host loopback, padrão 8100 |
| `CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE` | Bearer aplicação → Core |
| `CESAR_CORE_OMNIROUTE_AI_API_KEY_FILE` | Arquivo de credencial AI upstream |
| `CESAR_CORE_OMNIROUTE_SEARCH_API_KEY_FILE` | Arquivo distinto de credencial Search upstream |
| `CESAR_CORE_SEARXNG_SECRET_FILE` | Segredo interno do servidor SearXNG |
| `CESAR_CORE_AI_ENABLED` / `SEARCH_ENABLED` | Opt-in; padrões false |
| `CESAR_CORE_AI_DEFAULT_MODEL` | Target AI fixo configurado no OmniRoute (aplica-se a todo `ai_profile` sem override abaixo) |
| `CESAR_CORE_AI_USER_MODEL` | Nome do combo OmniRoute para `ai_profile=user` (ex.: `user-cascade`); sobrepõe `_DEFAULT_MODEL` só para esse perfil |
| `CESAR_CORE_AI_ADMIN_DEV_MODEL` | Nome do combo OmniRoute para `ai_profile=admin_dev` (ex.: `admin-dev-cascade`); sobrepõe `_DEFAULT_MODEL` só para esse perfil |
| `CESAR_CORE_AI_MODEL_ENFORCES_MAX_TOKENS` | Somente true após certificação real |
| `CESAR_CORE_AI_MAX_TOKENS_LIMIT` | Cap da policy, padrão 4096 |
| `CESAR_CORE_SEARCH_MAX_RESULTS_LIMIT` | Cap de saída, padrão 20 |
| `CESAR_CORE_SECURITY_AI_REQUESTS_PER_MINUTE` | Quota AI, padrão 60 |
| `CESAR_CORE_SECURITY_SEARCH_REQUESTS_PER_MINUTE` | Quota Search, padrão 60 |
| `CESAR_CORE_SECURITY_QUOTA_NAMESPACE` | Namespace estável, exclusivo por ambiente |
| `CESAR_CORE_OMNIROUTE_TIMEOUT_SECONDS` | Timeout upstream, padrão Compose 90s |

No nativo também existem `OMNIROUTE_BASE_URL`, `SECURITY_QUOTA_REDIS_URL`,
`SEARCH_DEFAULT_PROVIDER`, `SEARCH_PROVIDER_HEALTH_URL` e overrides por classe,
todos com prefixo `CESAR_CORE_`. No Compose, os endereços internos e o target
SearXNG são definidos pela topologia oficial. Não marque target pago como FREE.
AI e Search não recebem modelo/provider escolhido pelo body público -- o único
campo de identidade que o consumidor declara é `ai_profile` (`user` ou
`admin_dev`), usado pela policy para resolver o combo correto (ver
`docs/architecture/gg-oferta-core.md`, seção "Política de providers AI").

## Secrets e segurança

Arquivos locais ignorados pelo Git:

- `.secrets/ggoferta-core-client-dev`: segredo exclusivo do consumidor → Core
  no ambiente DEV. Outros ambientes devem usar arquivo e valor próprios.
- `.secrets/ggoferta-ai` e `.secrets/ggoferta-search`: chaves fornecidas pelo
  OmniRoute, independentes por capability e sem escopo administrativo.
- `.secrets/searxng`: valor aleatório forte para o servidor SearXNG.

Crie valores fora do terminal compartilhado/logs, com permissões restritas.
O consumidor recebe sua própria cópia da credencial Core; não reutilize chave
upstream. Nenhuma credencial Claudião deve ser criada. No Linux, arquivos do Core
precisam ser legíveis pelo UID/GID 10001, sem tornar o diretório público.
Compose secrets são mounts read-only, não um cofre criptografado.
O wrapper SearXNG lê seu arquivo e usa o mecanismo oficial `SEARXNG_SECRET`;
a imagem oficial não é reconstruída. O Core roda como usuário não-root,
filesystem read-only no Compose, sem capabilities Linux e sem Docker socket.

## Redis

Redis guarda **somente o estado de quota/janela do Core**, não produtos ou
missões de consumidores. A janela de 60s começa na primeira admissão. Excedente
não incrementa nem estende TTL e retorna 429 + Retry-After antes do upstream.
Restart Core não reinicia o saldo; instâncias compartilham Redis, namespace e policy.

[redis.conf](deploy/redis/redis.conf) fixa AOF, `appendfsync always`,
`no-appendfsync-on-rewrite no`, `noeviction` e volume persistente. Core confere
CONFIG GET/INFO antes de operar; nunca CONFIG SET. PING sozinho não prova
durabilidade. Mantemos always para não aceitar janela deliberada de perda de
admissões confirmadas em desastre Redis/host. Não é necessário apenas para crash
do Core quando Redis permanece vivo. Limites de hardware/failover e migração:
[ADR 0018](docs/adr/0018-persistent-quota-recovery.md).

## OmniRoute e SearXNG

OmniRoute **3.8.50 oficial**, fixado no digest certificado
`sha256:085c57adf499a8aaa9f35ccde95c0df9c11bd9ecd18d6c9edbf3b68b8079ba9d`.
Configuração e credenciais dos providers ficam no volume/runtime do OmniRoute.
AI usa o target configurado; Search usa uma conexão `searxng-search` com
`providerSpecificData.baseUrl=http://searxng:8080/search`. As 4 connections
reais de AI (Gemini USER, Gemini ADMIN/DEV, Groq ADMIN/DEV, OpenRouter
ADMIN/DEV) e os 2 combos (`user-cascade`, `admin-dev-cascade`) não fazem
parte deste Compose -- são provisionados uma vez por ambiente, com
procedimento determinístico e reproduzível em
`docs/operations/omniroute-ai-provider-provisioning.md`.

SearXNG tem JSON habilitado e acesso apenas interno. Motores externos podem
retornar CAPTCHA, rate limit ou ficar indisponíveis. `max_results` é garantido
na saída OmniRoute/Core; SearXNG pode adquirir mais resultados internamente.
Não confundir esse limite com cap da aquisição externa.

## Health e observabilidade

Não há dashboard administrativo próprio. A interface interativa da API está
em `/docs` (Swagger) e a referência em `/redoc`, na mesma porta do Core.
AI/Search continuam exigindo Bearer; o Swagger não contorna auth ou quota.

| Superfície | Significado |
|---|---|
| `GET /health` | Processo vivo, não verifica dependências |
| `GET /ready` | `ok` ou `degraded` para gateways configurados |
| `GET /v1/capabilities` | Inventário, não certificação de prontidão |
| `GET /metrics` | Prometheus; contadores operacionais por processo |
| `POST /v1/ai/generate` | Geração tipada autenticada |
| `POST /v1/search` | Busca autenticada e normalizada |

Redis inadequado: `quota_store_misconfigured`; indisponível/não verificável:
`quota_store_unavailable`. Gateways retornam 503; readiness informa o motivo
seguro. Quota esgotada não torna liveness/readiness inválidas. Gateways desligados
não exigem essas dependências. Healthcheck Docker testa o JSON de readiness,
não apenas HTTP 200. Não há dependência rígida de startup: Core pode iniciar
degraded e recuperar automaticamente. Logs vão a stdout/stderr, sem payload ou
secrets; métricas reiniciam com o processo, quota não.

## Atualização e rollback

Registre o digest atual antes de atualizar. Troque `CESAR_CORE_IMAGE`, faça
`docker compose pull cesar-core` e `docker compose up -d cesar-core`.
Valide readiness e contracts. Rollback usa o digest anterior e os mesmos
volumes/namespace/configuração compatível. Não remova volumes nem resete quota.
A 1.0.0 é a primeira release: não existe versão Docker anterior presumidamente
compatível. Backup/restore e troubleshooting estão no runbook.

## Desenvolvimento e testes

```sh
python -m pytest -m "not contract"
python -m ruff check .
git diff --check
python scripts/export_openapi.py
docker compose -f compose.yaml -f deploy/compose.dev.yaml build cesar-core
```

Contracts reais exigem infraestrutura e credenciais DEV; mocks não substituem
AI/Search reais. Há 22 contracts baseline e nove de quota/recovery/durabilidade.
Os harnesses históricos 118H são DEV Windows e nunca devem apontar para PROD.

**Testes são herméticos ao `.env` operacional (FASE E.2).** Uma fixture
autouse em `tests/conftest.py` (`_isolated_settings_env_file`) muda o cwd do
processo pra um diretório vazio por teste, então nenhuma classe de
configuração (`AIConfig`, `SearchConfig`, `FetchConfig`, `OmniRouteConfig`,
`SecurityConfig`, `AdminConfig` -- todas `env_file=".env"`, resolvido pelo
cwd, nunca pelo pacote) herda o `.env` real de DEV por acidente, não importa
de onde o `pytest` foi chamado. Isso nunca é opcional nem por convenção: o
`.env` real deste projeto tem chaves de várias capabilities, e cada
`BaseSettings` usa `extra="forbid"` -- uma classe "nua" que enxergasse esse
arquivo falharia com `ValidationError` para as chaves de prefixo alheio (ou,
pior, aceitaria silenciosamente um valor operacional real que o teste nunca
pediu). Variáveis de ambiente reais do processo continuam funcionando
normalmente (não são afetadas por este isolamento) -- só o arquivo `.env` é
neutralizado. Ver `tests/test_settings_env_isolation.py` para a prova
completa. Runtime real (containers, `python -m uvicorn ...`) nunca passa por
este `conftest.py` e continua lendo o `.env` normalmente.
[Contratos](contracts/README.md) e [validação 118H](docs/task-118h-rollout-resilience.md).
[Validação da distribuição 1.0.0](docs/deployment/release-1.0.0-validation.md).
Locks universais em `requirements/` têm versões e hashes; fontes em
`deploy/*requirements.in`. Atualizar lock exige nova validação nativa/container.

## Release privada

A tag anotada `v1.0.0` identifica o código. Tags Git não são movidas/recriadas.
O workflow `container-release.yml` dispara em SemVer estável `v*.*.*`, valida
a versão, builda linux/amd64 e publica usando GITHUB_TOKEN, sem PAT de publicação.
GHCR publica `1.0.0`, `1.0`, `1`, `latest` e `sha-<commit completo>`.
Tags de imagem são convenientes; **digest é a referência imutável**.
O package deve permanecer privado. Se uma tag falhar, não movê-la: decidir
release corretiva em novo commit/versão. A edição pública é uma tarefa futura.

## Projetos e serviços utilizados

URLs confirmadas nas imagens/documentação oficiais; não são forks do Core.

| Projeto | Função | Repositório oficial / baseline |
|---|---|---|
| OmniRoute | Gateway AI/Search | [diegosouzapw/OmniRoute](https://github.com/diegosouzapw/OmniRoute), 3.8.50 / digest acima |
| Redis | Quota durável | [redis/redis](https://github.com/redis/redis), 8.6.5-alpine; digest no Compose |
| SearXNG | General Web Search | [searxng/searxng](https://github.com/searxng/searxng), 2026.9.3-a1144dda3; digest no Compose |
| FastAPI | API HTTP | [fastapi/fastapi](https://github.com/fastapi/fastapi), 0.141.1 |
| Uvicorn | Servidor ASGI | [Kludex/uvicorn](https://github.com/Kludex/uvicorn), 0.52.4 |
| Pydantic | DTOs/configuração | [pydantic/pydantic](https://github.com/pydantic/pydantic), 2.13.5 |
| redis-py | Cliente Redis | [redis/redis-py](https://github.com/redis/redis-py), 6.4.0 |

Fontes de confirmação: labels OCI das imagens OmniRoute/SearXNG;
[docs SearXNG](https://docs.searxng.org/admin/installation-docker.html),
[FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://uvicorn.dev/) e
[redis-py](https://redis.readthedocs.io/). Dependências Python transitivas e seus
avisos de licença acompanham os pacotes instalados, sem relicenciamento.

## Licença

**Todos os direitos reservados.** Ver [LICENSE](LICENSE).
Distribuição privada; nenhuma licença open source é concedida para o Core.
Componentes externos mantêm suas próprias licenças.
