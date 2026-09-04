# TASK-119 — Control Plane

Implementação da interface administrativa persistente do César Core.

- Registry e políticas em SQLite WAL com migrations idempotentes.
- Credenciais dinâmicas HMAC/pepper, segredo exibido uma vez e rotação segura.
- Sessão Argon2id, HttpOnly/SameSite, CSRF, Origin/Host, rate limit e auditoria.
- Rollups de uso sem conteúdo de requests; quota corrente lida do Redis.
- Seis telas responsivas: overview, aplicações, chaves, uso, rotas e saúde.
- Tema claro/escuro, preferência local e tema do sistema no primeiro acesso.
- Frontend React/Vite/TypeScript/Tailwind, Radix e Lucide no mesmo artefato.
- Docker multi-stage; runtime final sem toolchain Node e volume separado.

Validação final deve registrar suíte Python, testes/build frontend, contratos
reais aplicáveis, build/inspeção Docker e QA visual desktop/mobile nos dois temas.

## Evidências DEV — 2026-09-04

- Regressão Python sem infraestrutura externa: 250 testes aprovados, cobertura
  total de 91,09% (mínimo exigido: 90%).
- Control Plane/security focados: 34 testes aprovados após a revisão final.
- Contracts reais contra OmniRoute/SearXNG/Redis oficiais em stack DEV isolada:
  22/22 de gateway, autenticação e autorização; 9/9 de quota persistente,
  totalizando 31/31. O harness passou a editar a policy de quota na autoridade
  SQLite, em vez de tentar alterar a configuração bootstrap por variável de
  ambiente.
- Frontend: 2/2 testes Vitest aprovados; TypeScript e Vite produziram os assets
  finais. `npm audit` não reportou vulnerabilidades.
- QA visual no navegador: seis telas, login, navegação, modais, tabelas e estados
  de loading/vazio/erro verificados em desktop e viewport estreito, nos temas
  claro e escuro. O console não apresentou erros.
- Docker: build multi-stage aprovado. A imagem roda como UID/GID 10001, contém
  os assets estáticos e não contém Node, npm, `package.json` nem fontes TS/TSX.
  O smoke test com root filesystem read-only confirmou `/health=ok`, SQLite no
  volume persistente e `/admin=503` quando a autenticação não é configurada.
- `docker compose -f compose.yaml -f deploy/compose.control-plane.yaml config`
  validou a composição opt-in do painel.
- A stack de contract descartável foi removida ao final. Nenhum secret, payload
  de AI/Search ou implementação do GG Oferta foi adicionado pela TASK-119.
