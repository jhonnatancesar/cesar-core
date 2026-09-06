# Operação Docker — César Core

## Pré-requisitos e arquivos

Docker com Linux containers, Compose v2, linux/amd64 e acesso autorizado ao
GHCR privado. Obtenha compose.yaml, deploy/ e .env.example da mesma tag.
Servidor de destino não precisa buildar nem instalar Python. Faça login no
GHCR com credencial de leitura, via password-stdin/cofre; nunca cole tokens
em comandos, relatórios ou arquivos versionados.

Copie .env.example para .env. Crie os arquivos em .secrets/ com permissões
restritas. Application Bearer é próprio do consumidor; chaves AI/Search são
emitidas pelo OmniRoute, em arquivos distintos, com menor privilégio. Não
reutilizar a credencial da aplicação como credencial upstream. SearXNG recebe
um segredo aleatório próprio. Não criar credencial Claudião.

No Linux, Core UID/GID 10001 deve ler seus arquivos; use grupo/permissões
restritas, não chmod 777. Compose secrets são bind mounts read-only, não um
cofre. A cópia de deploy e backups devem ter controle de acesso.

## Primeiro boot

1. Mantenha AI_ENABLED e SEARCH_ENABLED false durante o bootstrap.
2. Inicie dependências e abra temporariamente a UI OmniRoute apenas em loopback:

   ```sh
   docker compose -f compose.yaml -f deploy/compose.admin.yaml up -d redis searxng omniroute
   ```

3. Configure o OmniRoute oficial em http://127.0.0.1:20128. Habilite autenticação,
   emita chaves de API AI/Search sem escopo administrativo, grave-as nos arquivos
   locais esperados. Credenciais dos providers pertencem ao volume OmniRoute.
4. Configure conexão `searxng-search`, com
   `providerSpecificData.baseUrl=http://searxng:8080/search`. JSON está habilitado.
   Configure target AI fixo e certificado. Não declarar enforcement max_tokens
   para auto/best-free ou target não certificado. A baseline DEV certificou
   `oc/mimo-v2.5-free` (canonical `opencode/mimo-v2.5-free`); disponibilidade
   depende do provider. Não existe chave/modelo fornecido dentro da imagem.
5. Ative somente os gateways configurados no .env; forneça os quatro arquivos
   de segredo antes de iniciar o stack completo.
6. Remova a publicação administrativa recriando OmniRoute pelo Compose base:

   ```sh
   docker compose up -d --force-recreate omniroute
   docker compose pull cesar-core
   docker compose up -d
   docker compose ps
   curl http://127.0.0.1:8100/ready
   ```

Readiness deve conter status=ok **com gateways habilitados**. Gateways desligados
também dão ok, mas isso não certifica AI/Search. Teste as chamadas autenticadas.
Não imprimir Bearer no terminal compartilhado. Mantenha volumes ao recriar.

## Rede e health

Somente Core publica 127.0.0.1:8100. Redis e SearXNG não publicam portas; OmniRoute
somente no override administrativo temporário. Backend é rede interna; OmniRoute
e SearXNG também têm rede de saída. Core usa uma bridge ingress própria para
publicação loopback (bridge não bloqueia egress do Core). Dependências não
participam de ingress. Nomes entre containers: redis, omniroute,
searxng. Não trocar por localhost. Não montar socket Docker nos serviços.

/health verifica processo. /ready verifica dependências de gateways habilitados,
incluindo auth upstream e durabilidade Redis. HTTP 200 com degraded não é pronto;
healthcheck Core interpreta JSON. Redis PING é liveness, não certificação AOF.
Core verifica CONFIG GET/INFO e bloqueia gateway antes do upstream se inadequado.
Não executa CONFIG SET. Não há dependência rígida de ordem de startup.

Logs vão a stdout/stderr. Não compartilhar logs brutos das dependências sem
verificação local de segredos. Quota persiste; métricas são por processo.

## Volumes, backup e restore

Volumes Compose: `<projeto>_quota-data` (/data Redis) e
`<projeto>_omniroute-data` (/app/data). Confirme os nomes com docker volume inspect;
um COMPOSE_PROJECT_NAME diferente muda o volume e pode aparentar reset de quota.
Não usar down -v como rotina, não trocar namespace/DB durante restart.

Redis armazena contadores/janelas, não dados de negócio dos consumidores.
appendonly yes, appendfsync always, noeviction e no-appendfsync-on-rewrite no
estão versionados. AOF multiparte inclui manifesto, base e incrementais:
**copiar apenas um arquivo AOF não é backup consistente**.

Backup conservador: drene/pare Core, pare Redis de forma limpa e use o mecanismo
de snapshot/backup de volumes do operador para copiar **todo /data**, preservando
ownership e manifesto AOF. Mantenha cópia fora do volume, com acesso restrito.
Depois reinicie Redis e Core e valide readiness. Para OmniRoute, pare o serviço
antes do backup consistente de todo /app/data; esse volume contém credenciais.
Não incluir backups no Git nem nas imagens.

Restore: pare Core/Redis, restaure o diretório completo em volume apropriado,
preserve ownership e configuração, inicie Redis, verifique carregamento AOF e
então Core. Nunca restaure sobre um Redis escrevendo. Faça ensaio de restore em
ambiente isolado. Um backup antigo pode perder admissões recentes: mantenha o
tráfego drenado pelo menos até expirar a maior janela ativa (60s nesta versão)
antes de voltar a admitir requests. Não afirmar continuidade exata de quota
após perda do volume ou restore antigo. Fsync não protege contra perda física,
relógio incorreto ou failover assíncrono com perda.

## Atualização e rollback

Registre digest/configuração/namespace/volumes. Defina CESAR_CORE_IMAGE com
ghcr.io/jhonnatancesar/cesar-core@sha256:<digest>, faça pull e up -d cesar-core.
Verifique readiness e chamadas reais. Para rollback, repita com digest anterior
compatível e os mesmos volumes. Não fazer rollback de dados implicitamente.
1.0.0 é a primeira release: não se presume imagem anterior disponível.
Releases seguintes (1.1.0 em diante, ex.: Control Plane administrativo)
seguem o mesmo procedimento de digest acima — nenhuma migração especial de
volume foi exigida até aqui. Tags Git nunca são movidas. Falha do workflow
após tag requer decisão corretiva.

## Troubleshooting

- GHCR denied: conferir autorização read:packages e acesso ao package privado.
- quota_store_misconfigured: conferir os quatro parâmetros Redis; correção é
  operacional, não automática. Não desabilitar verificação para obter ok.
- quota_store_unavailable: conferir serviço, rede, ACL CONFIG GET/INFO/EVAL e disco.
- auth upstream degraded: conferir arquivos distintos, permissões e chaves válidas;
  não trocar REQUIRE_API_KEY para false para aparentar saúde.
- Search vazio: resultado vazio é válido; motores podem bloquear/CAPTCHA/rate limit.
  context7 é documentação técnica, não substituto universal.
- max_results limita saída OmniRoute/Core; não aquisição interna dos motores.
- Build DEV: override deploy/compose.dev.yaml. Falha de DNS/CDN deve ser corrigida
  na rede do build; nunca remover hashes/TLS ou embutir proxy/credenciais na imagem.
