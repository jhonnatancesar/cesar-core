# TASK-118H — rollout e resiliência DEV

Estado: validação DEV concluída e aprovada; fechamento da sequência 118.
Publicação e distribuição da primeira release tratadas separadamente; sem PROD.
Documento coordenador: `C:\AIShoppingAgent\AIShoppingAgent\docs\tasks\TASK-118H.md`.

## Baseline

Core `3578f2b`, GG Oferta `80dc135`, publicados em main. 118G validou 207 testes
Core não-contract, 22/22 contracts reais e Search GG→Core→OmniRoute→SearXNG.
Esses resultados são históricos, não reexecução da 118H. Rollout permanece opt-in;
nenhum deploy PROD autorizado ou executado.

## Preflight

Python oficial e credenciais DEV presentes. Após autorização para iniciar Docker,
Desktop já estava ativo; imagens certificadas confirmadas. Stack isolado 118H
com rede própria e banco copiado somente para teste; originais não reiniciados.

## Execução real da rodada

Harness `scripts/run_118h_contracts.py`, fases `core`, `gg`, `resilience`,
`recovery` e subprocesso `serve`. `scripts/stack_118h_dev.py up/down` provisiona
e limpa rede/containers/banco copiado/chaves temporárias, com guardas de ownership.
Não usar em PROD. Settings sem dotenv e configuração herdada removida.

Core: 22/22 contracts passaram (35,55s), após corrigir duas falhas de isolamento
no harness (configuração AI+Search não deve contaminar fixtures históricas).
GG: 2/2 contracts reais AI/Search passaram (26,45s). Resiliência: 2/2 paradas e
recuperações reais de OmniRoute/SearXNG passaram (48,09s), com readiness,
fallback Search e retorno ao provider principal. AI com OmniRoute parado retorna
503 normalizado. Teste focado do harness 1/1; Ruff dos arquivos novos passou.
Nenhuma assertion antiga ou implementação de domínio modificada.
Diff-check passou nos dois repositórios. Containers/rede e dados temporários
118H removidos, inclusive cópia da credencial. Banco original e prompt com hashes
inalterados; containers originais permaneceram parados.

## Continuação e resultado final

Restart do Core executado como processo real, novo PID, mesmos managers GG:
AI volta a gerar e Search retorna ao Core/SearXNG após fallback Firecrawl durante
a parada. Quota 1/min bloqueou AI/Search antes do socket upstream e reiniciou
com o Core, explicitando que é local/volátil. Credencial inválida e Search
sem capability retornaram 401/403 sem chamadas upstream.

Rollback AI/Search real: reload de Settings/factories, flags false, chamadas
à cascata anterior/Firecrawl sem tocar Core, depois flags true e Core/SearXNG.
Nenhum dado/migration alterado. Falhas 400/malformed/Firecrawl 503 injetadas por
HTTP local, identificadas como tal; Firecrawl tem tentativas finitas, sem loop.

Finais: 7/7 cenários complementares (61,76s), 22/22 Core (34,17s), 2/2 GG
(10,31s), 34/34 focados GG, 4/4 harness/guardas de recursos. Privacidade verificada
nos logs/traces novos, incluindo subprocessos, sem exibir valores. Não reaudita
histórico Codex nem cria credencial de Claudião, que continua RESERVED.

Runbook final: `C:\AIShoppingAgent\AIShoppingAgent\docs\operations\cesar-core-runbook.md`.
Inclui configuração, health, ordem não rígida de startup, matriz sintoma/causa/
verificação/ação, rollback exato e limites DEV→PROD. Última repetição de
dependências: 2/2 em 41,26s, incluindo erro AI no manager GG com OmniRoute fora.
Cleanup executado: rede, containers, banco copiado, chaves e logs temporários
removidos; hashes do banco original e prompt inalterados. Ruff Core completo e
Ruff dos testes novos GG passaram; diff-check passou nos dois repositórios.

## Limitações verificadas

`deployment/docker-compose.example.yml` é conceitual e não há Dockerfile.
Adapters GG atuais aceitam HTTP loopback, não hostnames de rede Docker ou HTTPS.
A topologia pretendida container→Core não deve ser anunciada como operacional
antes de implementar/validar o transporte correspondente de forma segura.

Na rodada inicial quota era por processo/em memória. Essa limitação foi
substituída na continuação Core-only pela ADR 0018; resultados de reset acima
são históricos, não representam a implementação atual.

Auth, capacidade, FREE_ONLY, enforcement certificado de max_tokens, cap de saída
max_results, Search vazio válido e separação Search/scrape são invariantes.

Sem alteração funcional de domínio, commit ou push nesta rodada. Histórico do Codex e
`TASK-118_CESAR_CORE_PROMPT.md` preservados; nenhum segredo reproduzido.

## Continuação Core-only — quota persistente e recovery

Implementação: Redis compartilhado por namespace, Lua atômico, TTL ancorado de
60s e AOF/fsync always obrigatório. Nenhum reset no startup. Redis fora ou
inseguro retorna 503 normalizado antes do upstream e degrada readiness; quota
excedida mantém 429, IDs e métricas, sem degradar health. ADR 0018 detalha ACL,
configuração e migração. Original Redis/OmniRoute/DB permanecem intocados.

Primeira regressão: 22/22 contracts Core com Redis real (32,92s), 228 testes
Core não-contract (95,73% de cobertura). Sete novos contracts reais passaram
(53,23s): concorrência entre threads e quatro processos; TTL/corrupção;
persistência Redis; troca real de PID Core com consumo 1→restart→2→429 e nenhum
socket upstream no excedente; Redis indisponível; OmniRoute e SearXNG down/up,
sem reiniciar Core para recuperar. Os primeiros erros eram exclusivamente
do harness (DTO sem requirements e launcher venv); foram corrigidos, sem
relaxar contratos. Nova execução reforça a persistência com SIGKILL do Redis
descartável em vez de shutdown gracioso.

Não existe circuito Core: recovery é nova tentativa, não open→half-open.
Circuito do GG e dependências externas não foram alterados. Documentação
futura GG registrada apenas no backlog; implementação/testes GG intocados nesta
continuação. Fases GG recovery anteriores não são revalidação da quota atual.

Repetição final reforçada: 7/7 em 53,55s, incluindo interrupção abrupta
(`SIGKILL`) do Redis e reconstrução do contador/TTL via AOF. Os resumos dos
contracts confirmaram `degraded/503 → ok/200` para cada dependência e os IDs
de correlação na rejeição 429. Saídas/logs novos dos processos Core foram
verificados contra as credenciais usadas, sem vazamento; logs temporários
removidos pelo fixture. Ruff completo e diff-check de ambos repositórios passaram.

Regressão final: 228/228 não-contract (95,73%). Cleanup final removeu somente
containers/rede/volume/banco/chaves temporários 118H. Redis original não foi
configurado nem ativado; gateways fora do harness exigem os requisitos da ADR
0018 antes de operação. Nenhum stage/commit/push ou PROD nesta continuação.

## Fechamento da verificação de durabilidade Redis

Core agora distingue configuração incompatível (`quota_store_misconfigured`)
de armazenamento indisponível/não verificável (`quota_store_unavailable`).
Ambos são 503 pré-upstream; `/ready` é degraded com `reason` opcional seguro.
Sucesso mantém o JSON anterior sem reason. OpenAPI foi regenerado somente
para esse campo no modelo existente. Não existe endpoint novo ou CONFIG SET.

Mantido appendfsync always pela garantia já adotada de admissões confirmadas
duráveis. Crash apenas do Core com Redis vivo não exige essa política; everysec
introduziria tolerância de aproximadamente 1s de perda em desastre Redis/host,
explicitamente NÃO aceita. ADR 0018 registra a distinção e limites de volume.

Validação desta rodada: 22/22 baseline (32,89s); 7/7 quota/recovery + 2/2 novos
de durabilidade (61,74s); 50 testes focados e 229 de regressão, cobertura 95,59%.
Redis adequado: ready ok, Search 200, quota preservada após novo PID e 429 sem
upstream. Redis parado: degraded/unavailable e 503 sem upstream. Redis adicional
com AOF=no ou AOF=yes/fsync=everysec: PING verdadeiro, startup Core degraded,
AI/Search 503 misconfigured, nenhum contador criado/socket upstream, configuração
Redis inalterada. Os servidores inadequados foram iniciados com esses parâmetros
em containers descartáveis: nem o harness executou CONFIG SET.

O primeiro replay identificou corrida no teste AOF: Docker start não implica
Redis pronto. Harness passou a aguardar até 10s com probes somente de leitura,
sem retry de consumo; repetição completa dos nove cenários aprovada. Asserts de
contador/TTL permaneceram. Logs novos passaram na verificação de credenciais.
Ruff e diff-check aprovados. GG Oferta não recebeu alteração nesta rodada.
