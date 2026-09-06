# Integração GG Oferta ↔ César Core em DEV

Este é o procedimento DEV para colocar os dois repositórios em funcionamento
no ambiente local. Ele não altera PROD e não coloca credenciais em `.env`, Git,
comandos, logs ou documentação.

A arquitetura e a decisão de topologia canônicas estão em
[`docs/architecture/gg-oferta-core.md`](../architecture/gg-oferta-core.md).

## Princípio operacional

O César Core é o centro da integração e a fonte de verdade. É nele que ficam:

- identidade e estado da aplicação `gg_oferta`;
- credenciais aceitas, capabilities e autorização;
- policies por purpose e service class;
- quotas e contadores persistentes;
- seleção/certificação de targets AI e Search;
- `FREE_ONLY`, `max_tokens`, `max_results`, readiness e observabilidade;
- referências lógicas de targets e configuração dos gateways, Redis e health
  do SearXNG.

As conexões reais e credenciais de providers pertencem ao runtime/volume do
OmniRoute. Configurar `CESAR_CORE_AI_DEFAULT_MODEL` ou
`CESAR_CORE_SEARCH_DEFAULT_PROVIDER` não cria essas conexões.

No caminho central, o GG Oferta não replica nem decide essas políticas. Ele
conhece a URL do Core, lê sua própria cópia do Bearer, envia
`service`/`purpose`/requirements e controla flags locais de rollout. Caminhos
legados e flags de fallback ainda existem durante a transição, mas não mudam a
decisão central quando uma chamada passa pelo Core.

## Fluxo e diretórios

```text
GG Oferta
  ├── AIProviderManager ── POST /v1/ai/generate ──┐
  └── WebSearchManager ── POST /v1/search ────────┤
                                                   ▼
                                             César Core
                                               ├── Redis (quota)
                                               └── OmniRoute
                                                    ├── AI target
                                                    └── SearXNG
```

Os comandos abaixo assumem:

- César Core em `C:\cesar-core`;
- GG Oferta em `C:\AIShoppingAgent\AIShoppingAgent`;
- PowerShell no Windows;
- Docker Desktop com Linux containers e Compose v2.

## 1. Credencial entre as aplicações

A mesma credencial DEV deve existir em dois arquivos locais separados:

```text
C:\cesar-core\.secrets\ggoferta-core-client-dev
C:\AIShoppingAgent\AIShoppingAgent\.secrets\cesar-core-client-dev
```

O primeiro arquivo é lido pelo Core para autenticar `gg_oferta`; o segundo é
lido pelo cliente do GG Oferta para montar o Bearer. Ambos os diretórios
`.secrets/` são ignorados pelo Git. Não reutilize credenciais do OmniRoute,
Firecrawl, banco, administração ou PROD.

Valide somente existência e rastreamento, sem imprimir o conteúdo:

```powershell
Test-Path C:\cesar-core\.secrets\ggoferta-core-client-dev
Test-Path C:\AIShoppingAgent\AIShoppingAgent\.secrets\cesar-core-client-dev
git -C C:\cesar-core check-ignore .secrets/ggoferta-core-client-dev
git -C C:\AIShoppingAgent\AIShoppingAgent check-ignore .secrets/cesar-core-client-dev
```

## 2. Configurar o César Core

Crie `C:\cesar-core\.env` a partir de `.env.example` se ele ainda não existir:

```powershell
Set-Location C:\cesar-core
Copy-Item .env.example .env
```

Confirme no `.env` o caminho do Bearer do consumidor:

```dotenv
CESAR_CORE_SECURITY_GG_OFERTA_API_KEY_FILE=.secrets/ggoferta-core-client-dev
```

Para habilitar cada gateway, configure também os arquivos upstream e os targets
reais certificados. Os valores abaixo são configuração, não segredos:

```dotenv
CESAR_CORE_AI_ENABLED=true
CESAR_CORE_AI_DEFAULT_MODEL=<target-ai-certificado-no-omniroute>
CESAR_CORE_AI_MODEL_ENFORCES_MAX_TOKENS=true
CESAR_CORE_SEARCH_ENABLED=true
CESAR_CORE_SEARCH_DEFAULT_PROVIDER=searxng-search
```

Os arquivos abaixo precisam existir antes da subida; seus conteúdos vêm do
OmniRoute/SearXNG e não devem ser copiados para `.env`:

```text
.secrets/ggoferta-ai
.secrets/ggoferta-search
.secrets/searxng
```

O Compose oficial sobe Core, Redis persistente, OmniRoute 3.8.50 e SearXNG:

```powershell
docker compose -f compose.yaml -f deploy/compose.dev.yaml config --quiet
docker compose -f compose.yaml -f deploy/compose.dev.yaml up -d --build
docker compose -f compose.yaml -f deploy/compose.dev.yaml ps
```

O Core fica publicado somente em `http://127.0.0.1:8100`. Redis, OmniRoute e
SearXNG permanecem internos ao Compose. A configuração dos targets/conexões no
OmniRoute continua sendo feita pelo mecanismo oficial dele; o Core não a cria
automaticamente.

## 3. Validar o Core antes de ligar o consumidor

```powershell
Invoke-RestMethod http://127.0.0.1:8100/health
Invoke-RestMethod http://127.0.0.1:8100/ready
Invoke-RestMethod http://127.0.0.1:8100/v1/capabilities
```

Critérios:

- `/health` confirma que o processo está vivo;
- `/ready` deve estar `ok` para os gateways habilitados;
- Redis ausente ou sem AOF/`appendfsync always` deixa quota/readiness degraded;
- capability habilitada precisa estar disponível para `gg_oferta`;
- não prossiga enquanto readiness explicar dependência ou credencial inválida.

Valide autenticação sem registrar o Bearer. O PowerShell lê o arquivo em memória;
o valor não aparece na linha de comando nem na resposta:

```powershell
$coreToken = Get-Content C:\AIShoppingAgent\AIShoppingAgent\.secrets\cesar-core-client-dev -Raw
$headers = @{
  Authorization = "Bearer $coreToken"
  "X-Purpose" = "market_research"
  "X-Service" = "backend"
}

# Sem Bearer deve retornar 401.
try {
  Invoke-RestMethod -Method Post http://127.0.0.1:8100/v1/search `
    -ContentType application/json `
    -Body '{"query":"Python official documentation","max_results":1,"requirements":{"service_class":"economy","cost_policy":"free_only"}}'
} catch { $_.Exception.Response.StatusCode.value__ }

# Bearer DEV correto deve autenticar gg_oferta e executar Search.
Invoke-RestMethod -Method Post http://127.0.0.1:8100/v1/search `
  -Headers $headers -ContentType application/json `
  -Body '{"query":"Python official documentation","max_results":1,"requirements":{"service_class":"economy","cost_policy":"free_only"}}'
```

Para AI, use apenas se o target configurado estiver pronto e certificado:

```powershell
$headers["X-Purpose"] = "chat"
Invoke-RestMethod -Method Post http://127.0.0.1:8100/v1/ai/generate `
  -Headers $headers -ContentType application/json `
  -Body '{"messages":[{"role":"user","content":"Responda somente OK."}],"max_tokens":512,"requirements":{"service_class":"economy","cost_policy":"free_only"}}'
```

Remova as variáveis da sessão após os probes:

```powershell
Remove-Variable coreToken, headers
```

## 4. Conectar o GG Oferta como consumidor

O `Settings` do backend lê o arquivo local
`C:\AIShoppingAgent\AIShoppingAgent\backend\.env`. Para a execução nativa,
copie o exemplo se esse arquivo ainda não existir e edite essa cópia:

```powershell
Set-Location C:\AIShoppingAgent\AIShoppingAgent\backend
Copy-Item .env.example .env
```

Confirme estas linhas em `backend\.env`:

```dotenv
AISHOPPING_CESAR_CORE_BASE_URL=http://127.0.0.1:8100
AISHOPPING_CESAR_CORE_API_KEY_FILE=C:/AIShoppingAgent/AIShoppingAgent/.secrets/cesar-core-client-dev
AISHOPPING_CESAR_CORE_SERVICE=backend
AISHOPPING_CESAR_CORE_SERVICE_CLASS=economy
AISHOPPING_CESAR_CORE_MAX_TOKENS=1024
AISHOPPING_CESAR_CORE_TIMEOUT_SECONDS=90
AISHOPPING_CESAR_CORE_SEARCH_TIMEOUT_SECONDS=30
AISHOPPING_CESAR_CORE_AI_ENABLED=true
AISHOPPING_CESAR_CORE_SEARCH_ENABLED=true
AISHOPPING_CESAR_CORE_SEARCH_FALLBACK_ENABLED=false
AISHOPPING_CESAR_CORE_DISASTER_FALLBACK_ENABLED=false
```

Ative apenas gateways que estejam `ok` no Core. Os fallbacks permanecem
desligados no primeiro teste para que uma falha de integração não seja mascarada.
O fallback Firecrawl de Search só deve ser habilitado depois e apenas para
indisponibilidade elegível; scrape continua sendo enriquecimento separado.

O caminho diretamente funcional com a configuração atual é executar o backend
do GG Oferta nativamente. Ele lê `backend\.env` e alcança o Core pelo loopback:

```powershell
Set-Location C:\AIShoppingAgent\AIShoppingAgent\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

O `compose.yaml` atual do GG Oferta ainda não encaminha as variáveis
`AISHOPPING_CESAR_CORE_*` nem monta `cesar-core-client-dev` nos serviços. Por
isso, não use `docker compose up` como prova desta integração sem antes existir
um wiring versionado que:

- monte `.secrets/cesar-core-client-dev` como secret read-only;
- defina `AISHOPPING_CESAR_CORE_API_KEY_FILE` para o caminho interno do mount;
- encaminhe as flags, URL, service, class e timeouts aos serviços consumidores;
- implemente a rede externa `cesar-platform` decidida na arquitetura canônica e
  valide explicitamente o transporte container → Core.

Esse wiring não deve ser improvisado no manual, não deve usar
`host.docker.internal` como arquitetura substituta e não deve incluir o Bearer
diretamente nas variáveis do Compose. `127.0.0.1` dentro do container aponta
para o próprio container.

## 5. Prova end-to-end

Execute uma operação curta de AI pelo `AIProviderManager` e uma pesquisa estável
pelo `WebSearchManager` do GG Oferta. A evidência esperada é:

- identidade resolvida no Core como `gg_oferta`;
- AI com provider normalizado `cesar_core` e upstream OmniRoute;
- Search: GG Oferta → Core → OmniRoute → SearXNG;
- `max_tokens`, `max_results`, quota e `FREE_ONLY` respeitados;
- nenhuma credencial em logs, traces ou métricas;
- Search vazia continua sucesso válido;
- Firecrawl Search não é chamado em zero-result, 401, 403 ou quota;
- Firecrawl scrape, quando necessário, permanece enriquecimento de URLs já
  encontradas, não fallback de Search.

Durante o teste, acompanhe somente metadados seguros:

```powershell
docker compose -f C:\cesar-core\compose.yaml logs --since=5m cesar-core
# Para execução nativa, acompanhe o stdout do terminal do backend/worker.
```

## 6. Diagnóstico rápido

| Sintoma | Verificação |
|---|---|
| `401` | arquivos dos dois lados não têm o mesmo valor, caminho não foi montado ou processo não reiniciou |
| `403` | `gg_oferta` sem capability/purpose autorizados |
| `429` | quota da aplicação esgotada; não habilitar fallback para contornar policy |
| `503 quota_store_*` | Redis ausente ou sem a durabilidade exigida |
| Core saudável, gateway degraded | credencial/target upstream ou SearXNG não está pronto |
| erro de conexão a `127.0.0.1` no container | o Compose GG ainda não implementa a topologia `cesar-platform`; usar o processo GG nativo na FASE 0/A, sem improvisar endereço |
| GG Oferta usa provider antigo | flag ainda false ou processo não recarregou o `.env` |

## 7. Desligar sem apagar dados

No `.env` do GG Oferta, volte as flags para `false` e reinicie seus processos:

```dotenv
AISHOPPING_CESAR_CORE_AI_ENABLED=false
AISHOPPING_CESAR_CORE_SEARCH_ENABLED=false
```

Para parar o Core sem remover volumes:

```powershell
docker compose -f C:\cesar-core\compose.yaml -f C:\cesar-core\deploy\compose.dev.yaml down
```

Não use `down -v`: quota Redis, configuração do OmniRoute e dados do Control
Plane usam volumes persistentes.
