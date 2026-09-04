# Pré-release 1.0.0 — validação DEV

Data: 2026-09-04. Sem operação em PROD ou alteração de implementação GG Oferta.
Repositório confirmado PRIVATE; licença própria com todos os direitos reservados.

## Resultados anteriores à tag

- 232 testes não-contract: 229 regressões + 3 guardas de distribuição; cobertura 95,59%.
- 22/22 contracts baseline com OmniRoute oficial 3.8.50.
- 9/9 contracts Redis: sete quota/recovery e dois Redis inadequado.
- Ruff e git diff --check aprovados.
- Build linux/amd64 concluído, dependências com hashes e bases pinadas.
- Imagem local: 62.615.933 bytes reportados pelo Engine; UID/GID 10001:10001.
- Smoke com filesystem read-only: versão 1.0.0, health/ready ok com gateways
  desligados; não usado como prova de funcionamento upstream.

## Stack limpa com imagem, não Python do host

Projeto Compose descartável `cesar-release-validation`; configurações/secrets
DEV fornecidos em runtime e banco OmniRoute copiado para diretório isolado.
Redis com volume próprio. Nenhuma alteração da instância/banco original.
Core container → Redis/OmniRoute → SearXNG/providers, usando compose.yaml oficial.

- Gateways AI/Search habilitados: health=ok, readiness=ok.
- Redis: AOF=yes, appendfsync=always, noeviction, no-appendfsync-on-rewrite=no.
- AI, messages tipadas: texto `CESAR_RELEASE_OK`; max_tokens=512;
  usage prompt=31, completion=23, total=54; upstream request ID presente.
- Target solicitado `oc/mimo-v2.5-free`; modelo retornado no contrato Core
  `mimo-v2.5-free`. A certificação histórica registra canonical
  `opencode/mimo-v2.5-free`; não houve alteração de alias.
- Search: `Python programming language official documentation`, max_results=3,
  provider `searxng-search`, três resultados, posições 1–3, título/URL/snippet.
  Primeiro resultado: Our Documentation | Python.org, https://www.python.org/doc/.
  usage queries_used=1, cost=0, total disponível=20; limite é da saída, não da
  aquisição interna SearXNG. Campo max_results continua encaminhado pelo adapter
  certificado nos contracts baseline, sem mudança nesta release.
- Cache: primeira chamada false, segunda true, resultados idênticos.
- Quota Search=2: duas admissões, próxima chamada 429 quota_exceeded, sem
  upstream_request_id. Contador Redis permaneceu 2; restart apenas Core e restart
  do stack preservaram contador e TTL, com novas rejeições 429. Restavam 40.336ms
  da janela ao final; não se estendeu/resetou a janela para fazer o teste passar.
- Contracts de quota complementam a prova verificando ausência de novo socket
  upstream em rejeição, concorrência multiprocesso, SIGKILL Redis e recovery.
- Credenciais usadas ausentes nas respostas/logs reais e no arquivo da imagem
  com todas as camadas, verificado em memória sem imprimir valores.
- Contexto Docker allowlist exclui Git, secrets, prompt, testes e artefatos locais.

## Ajustes encontrados na prova

DNS Docker resolvia files.pythonhosted.org para endereço inacessível. Build local
usou --add-host com resolução pública verificada; Dockerfile não contém IP fixo,
credencial, proxy nem relaxamento TLS/hashes. Core apenas em rede internal não
publicava a porta no Docker Desktop: adicionada bridge ingress exclusiva do Core,
com porta loopback. Backend continua interno; dependências não publicam portas.

Harness local passou a aguardar readiness após recriação e ler logs como UTF-8
em vez do padrão Windows cp1252. Provas de AI/Search/quota passaram antes do
ajuste de decodificação; verificação de logs/camadas foi executada separadamente
com sucesso. Uma execução inicial de pytest sofreu permissões no temp padrão;
reexecução com basetemp isolado no workspace passou integralmente. Nenhuma dessas
falhas exigiu alterar domínio, auth, quota, adapters ou semântica de respostas.

## Publicação e limites

Publicação concluída: [Actions 33902224388](https://github.com/jhonnatancesar/cesar-core/actions/runs/33902224388),
todos os passos aprovados, incluindo verificação de package privado e pull CI.
Tag anotada `v1.0.0`, imutável, aponta para
`b22a5e88b8767657ce919b03886a52f5b2645cf3`.

Imagem: `ghcr.io/jhonnatancesar/cesar-core`.
Digest publicado e confirmado pelo pull local:
`sha256:e96feababeec5626ecf0fd696e0c46188c8e0009cbd0092166d91088125bf3ad`.
Tags: `1.0.0`, `1.0`, `1`, `latest`,
`sha-b22a5e88b8767657ce919b03886a52f5b2645cf3`.
Package PRIVATE confirmado pela API do GitHub após publicação.

A imagem baixada foi executada **por esse digest** no Compose DEV. Versão
1.0.0, UID 10001, health/ready ok com gateways habilitados. AI retornou
CESAR_RELEASE_OK, usage prompt=31/completion=24/total=55, cap=512. Search retornou
os mesmos três resultados normalizados, primeira chamada cached=false e segunda
true. Quota 429, restart Core e restart stack preservaram contador/TTL (44.841ms
restantes). Verificação dos secrets usados nas respostas/logs reais passou.
Não se usou somente o cache da imagem local como prova de publicação.

O digest CI difere do local por metadata/revision/attestation. Este complemento
documental posterior à publicação não move nem recria a tag.

Sem dashboard, TLS externo, HA Redis ou distribuição pública genérica nesta
release. Disponibilidade dos providers gratuitos é externa. O consumidor precisa
retomar seus contracts DEV: quota não reseta mais em restart e erros do store
não devem ser confundidos inadvertidamente com indisponibilidade de Search.
