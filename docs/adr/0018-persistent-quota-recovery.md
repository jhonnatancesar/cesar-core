# ADR 0018 — quota compartilhada durável e recovery do Core

## Status e escopo

Implementada, validada em DEV e aprovada na continuação da TASK-118H.
Substitui somente a limitação de quota volátil da ADR 0016. Nenhum deploy,
commit, mudança GG Oferta, Firecrawl, Market Research ou frontend.

## Decisão

A quota anterior era um dicionário com Lock/monotonic em cada processo:
restart resetava a janela e réplicas poderiam multiplicar o limite. Redis já
é recurso da plataforma (`omniroute-redis`, imagem Redis 8.6.5-alpine); o Core
passa a utilizar seu próprio namespace e chave por aplicação/capability, sem
usar o banco de negócio GG nem o banco interno OmniRoute. Não foi criado um
serviço permanente. A validação usa clone Redis descartável com volume próprio.

Um script Lua faz GET/PTTL/SET PX/INCR atomicamente. A primeira admissão ancora
a janela de 60 segundos; outras admissões incrementam sem renovar TTL.
Excedente não incrementa nem renova TTL e retorna 429 + Retry-After arredondado
para cima. O relógio/expiração é do Redis; trocar PID/instância do Core não
recria janela. Quotas AI/Search independentes e gate após auth/capability e
antes de manager/upstream permanecem. Contam-se admissões, inclusive requests
que posteriormente falham em validação/policy/provider: não há reembolso novo.

Redis deve ter volume persistente, AOF habilitado, appendfsync always,
no-appendfsync-on-rewrite no e noeviction. Esses requisitos e o estado AOF são
verificados antes de consumir e no probe de readiness. Core nunca executa
CONFIG SET. Chave corrompida/sem TTL, falha de conexão/escrita/leitura, timeout
falham fechados (`503 quota_store_unavailable`); configuração incompatível
identificada por CONFIG GET retorna `503 quota_store_misconfigured`, ambos
antes do upstream. Nenhuma alternativa em memória e nenhum retry automático
de EVAL: uma resposta perdida pode ter consumido quota, mas não autoriza
repetição nem consumo upstream. Sacrifica-se disponibilidade para preservar limite.

Não adicionar um novo circuito local sobre o Redis: cada próxima requisição
ou probe tenta novamente, com timeout de conexão/comando (padrão 1 segundo).
Operações síncronas de quota rodam na dependency FastAPI em threadpool; o probe
usa run_in_threadpool. Conexões são encerradas por operação.

## Configuração e operação

### Revisão explícita da garantia de fsync

O requisito estrito de crash/restart **somente do Core**, mantendo Redis vivo,
e compartilhamento entre processos não exige `always`: os contadores já estão
fora do Core. No entanto, a ADR adotou também persistência das admissões
confirmadas diante de falha do armazenamento. Mantemos **appendfsync always**
para não enfraquecer essa garantia aprovada: não é aceita janela deliberada de
perda de escritas confirmadas. `everysec` seria suficiente para o primeiro
requisito, mas introduziria aproximadamente um segundo de perda em desastre
Redis/host, podendo restituir quota já consumida. Essa tolerância NÃO foi adotada.
Não se trata de afirmar que always é indispensável para todo restart Core.
Continuam válidas as ressalvas de disco/volume/backup/failover abaixo.

### Verificação e readiness

Core usa CONFIG GET dos quatro parâmetros e INFO persistence para o estado
de escrita AOF; PING não certifica durabilidade. Configuração divergente ou
parâmetro obrigatório ausente é `quota_store_misconfigured`; falha de conexão,
ACL que impeça verificar requisitos ou falha de escrita é `quota_store_unavailable`.
Nunca reporta adequação quando não consegue verificar. Não executa CONFIG SET.

O processo pode iniciar vivo com Redis ruim, mas `/ready` não indica aptidão:
`status=degraded`, `core=available` (processo vivo) e `reason` com o código seguro.
O modelo não tinha detail/reason: foi acrescentado apenas `reason` opcional ao
endpoint existente, omitido nas respostas sem falha de quota e documentado no
OpenAPI. Não há URL, credencial, exceção Redis bruta nem configuração secreta.
Cada gateway repete a verificação antes de consumir, independentemente de o
cliente/orquestrador consultar readiness. Não existe intervalo de startup
em que ignorar o probe autorize consumo. Correção operacional recupera nas
próximas chamadas sem reset da quota. Gateways desligados não exigem Redis.

- `CESAR_CORE_SECURITY_QUOTA_REDIS_URL`: redis/rediss, sem senha/usuário na URL
  e sem parâmetros de conexão arbitrários. Credencial via PASSWORD_FILE e
  username opcional; ver `.env.example`.
- `CESAR_CORE_SECURITY_QUOTA_NAMESPACE`: estável e exclusivo por ambiente.
  Todas as réplicas devem compartilhar Redis, namespace e limites da policy.
  Alterar namespace/DB/endereço equivale a trocar o saldo: não fazê-lo durante
  restart/rollout. Redis standalone, não um cluster multi-master.
- ACL operacional precisa GET, SET, INCR, PTTL, EVAL nas chaves do namespace,
  INFO persistence e CONFIG GET (somente leitura). Não conceder CONFIG SET,
  FLUSHDB/FLUSHALL ou DELETE em runtime. SCAN/DELETE são usados apenas pelo
  reset de testes, guardado por namespace `cesar-core:test:`; não há reset no startup.
- Volume, disco e relógio Redis precisam ser confiáveis. Não há promessa de
  sobreviver à perda do volume, restauração de backup antigo, remoção de chaves
  por administrador ou failover com perda de escrita em réplica assíncrona.
  AOF everysec/RDB não satisfazem esta decisão. Não anunciar HA não implementada.
- Redis original local permaneceu parado/intocado. Antes de habilitar gateways
  nesse serviço, operação deve verificar/adotar os requisitos de durabilidade.
  Esta tarefa não autoriza reconfigurar infraestrutura compartilhada/PROD.
- Migração memória→Redis não pode recuperar contadores que só existiam em RAM.
  Para ativação sem sobreposição, drenar instâncias antigas, aguardar a janela
  antiga máxima (60s) e só então servir com namespace persistente. É procedimento
  futuro de rollout; não executado em PROD.
- Métricas permanecem por processo para scraping Prometheus; a quota, não.
  Rejeição aparece no contador HTTP com aplicação, path e status 429/503;
  request/correlation IDs são preservados. Reiniciar métricas não reinicia quota.

## Circuit breaker: auditoria delimitada

O Core **não possui circuit breaker**. `omniroute/client.py` faz uma tentativa
HTTP, normaliza erro e encerra o transporte; não há estado open/half-open,
cooldown ou janela para travar chamadas após recuperação. Managers/providers
Core não mantêm circuito. Portanto não existe transição de circuito Core a
certificar; o que os contracts provam é falha normalizada e recovery real.
Nenhuma proteção foi removida e nenhum circuito adicional foi inventado.

O circuito identificado é do **GG Oferta**, em `backend/app/core/resilience.py`,
usado por `backend/app/ai_provider/manager.py`, por chave de provider/operação.
Padrões: 5 falhas transitórias, open por 30s, próxima tentativa vira half-open
com uma única sonda; sucesso fecha; falha transitória reabre por outra janela;
falha não transitória limpa o estado. É configuração do consumidor, não do Core,
e ficou intocada. Estados internos do OmniRoute são outra responsabilidade.

Core distingue 401/403 de erro de cliente e de 5xx/timeout/conexão. Nada nesta
decisão transforma 4xx em falha transitória. Queda OmniRoute/SearXNG é observada
em `/ready` e nos requests; retorno é verificado por novos requests no mesmo PID,
inclusive depois de um restart anterior do Core.

## Health e contratos

Liveness `/health` independe de Redis/OmniRoute/SearXNG. Readiness exige
dependências habilitadas; Redis fora/inseguro degrada; saldo esgotado não.
Probes não consomem quota e recuperação não exige restart geral.

Teste novo real e suite anterior são complementares: 22 contracts históricos
preservam auth/policy/AI/Search; sete novos verificam persistência, concorrência,
restart e recovery; dois adicionais provam PING positivo com AOF desligado ou
fsync everysec e rejeição de ambos gateways sem upstream. O teste histórico GG que esperava reset de quota é evidência
da limitação antiga e não vale mais como comportamento esperado; ficou sem
alteração e não foi reexecutado, conforme escopo Core-only desta rodada.

## Base técnica

[Redis Lua atomic execution](https://redis.io/docs/latest/develop/programmability/eval-intro/)
e [Redis AOF persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/):
execução atômica para o gate; fsync always para confirmação durável. Durabilidade
continua dependendo do volume/dispositivo e não substitui operação/backup.
