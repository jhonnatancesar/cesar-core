# ADR 0019 — distribuição Docker e release privada

## Decisão

Docker é a execução operacional recomendada; Python/venv continua suportado
para DEV. Ambos instalam a mesma codebase. Não existe branch Docker nem fork
do domínio. A primeira versão é 1.0.0, com todos os direitos reservados.
Repositório e package GHCR permanecem privados.

Quatro imagens independentes: Core, Redis, OmniRoute e SearXNG. A imagem oficial
OmniRoute 3.8.50 mantém o digest certificado na ADR 0012, sem customização.
Dependências Python têm locks com hashes; bases e serviços têm digests fixos.
Core usa wheel, UID/GID 10001, runtime read-only, sinais para shutdown e
readiness JSON no healthcheck. Contexto de build é uma allowlist sem secrets.

Compose operacional puxa imagem publicada; override DEV apenas acrescenta
build local. Backend interno, Redis sem porta host e rede egress para
OmniRoute/SearXNG. Core usa bridge ingress para publicar loopback; essa rede
também permite saída, sem promessa de firewall egress. A prova em Docker Desktop
mostrou que porta publicada com Core somente na rede internal não é acessível.
Acesso remoto/TLS exige decisão própria.
Credenciais são arquivos externos read-only. Redis possui volume AOF/always,
sem enfraquecer a verificação runtime da ADR 0018. Startup não promete dependências
prontas: degraded e recuperação são propriedades do Core.

## Release

Tags Git anotadas SemVer são imutáveis. Actions usa GITHUB_TOKEN com contents:read
e packages:write; publica linux/amd64, tags SemVer/latest/sha e registra digest.
Digest é autoridade de deployment. Antes da tag: testes, contracts reais,
imagem e stack limpa; depois: pull e smoke da imagem publicada. Falha depois
da tag exige decisão de release corretiva, nunca mover a tag.

Mudanças futuras para distribuição pública/genérica são outro escopo. Esta
release não implanta ou altera consumidor/PROD. Operação, backup e rollback:
[runbook Docker](../deployment/docker.md).
