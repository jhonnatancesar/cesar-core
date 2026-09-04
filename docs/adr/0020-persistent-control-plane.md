# ADR 0020 — Control Plane persistente e seguro

Status: aceita — 2026-09-04

## Decisão

O César Core incorpora uma interface administrativa em `/admin` e uma API
privada em `/admin/api`. O registry de aplicações, capabilities, políticas de
quota, credenciais dinâmicas, sessões, auditoria e rollups horários passam a ter
SQLite em WAL como fonte persistente. O processo continua deliberadamente
single-instance; contadores concorrentes de quota permanecem no Redis durável.

As migrations são SQL numeradas, transacionais, idempotentes e aplicadas no
startup. Alembic não foi adotado: o projeto não usa ORM, o schema é pequeno e o
runner explícito reduz dependências e superfície operacional. Um volume
`control-plane-data` preserva SQLite entre recriações do container.

`gg_oferta` e `claudiao` são bootstrap por `INSERT OR IGNORE`, nunca sobrescrevem
edições. Claudião permanece `RESERVED`, protegido e sem credencial. Novas
aplicações nascem `DISABLED`; ativação exige capability, quota positiva e
credencial ativa. Aplicações não são apagadas.

Credenciais usam o envelope `cc_<credential_id>.<secret>`. O ID público localiza
o registro e o servidor compara HMAC-SHA-256 com pepper lido via `*_FILE`.
SQLite nunca recebe o segredo em claro; ele aparece apenas na resposta de
criação. Rotação cria uma segunda credencial antes da revogação explícita da
anterior. O arquivo legado do GG Oferta permanece aceito somente para leitura.

O único administrador autentica com hash Argon2id via arquivo. A sessão é um
token opaco cujo SHA-256 é persistido, em cookie HttpOnly, SameSite=Strict e
Secure sob HTTPS. Escritas também exigem CSRF, Origin e Host exatos. Login é
limitado no Redis e falha fechado se essa proteção estiver indisponível.
Expirações absoluta e por inatividade são independentes. Toda mutação gera
auditoria sem segredos.

Uso é agregado por hora, aplicação, capability, status, provider e cache. Não
há histórico de payloads nem eventos individuais por padrão. Os agregados têm
retenção configurável (30 dias por padrão) e os buckets expirados são removidos
no startup. Rotas são derivadas do OpenAPI runtime. O painel oferece seis telas
e tema claro/escuro; a preferência visual fica apenas no navegador.

## Consequências

O Control Plane falha com `503` quando sua autenticação está incompleta. O
runtime Docker final não contém Node, npm nem fontes do frontend: um estágio
Node fixado por digest compila os assets, incorporados ao wheel Python. O volume
é preparado para UID/GID não-root 10001.
