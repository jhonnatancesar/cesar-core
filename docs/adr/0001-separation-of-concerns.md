# ADR 0001 -- Separação de responsabilidades por pasta

## Status

Aceito (TASK-118A).

## Contexto

O César Core precisa crescer para cobrir identidade de aplicação, política
de custo/qualidade, contratos de AI/Search, integração com OmniRoute,
segurança, telemetria e health -- sem virar um monólito com `utils.py`/
`helpers.py`/`services.py` genéricos onde tudo é despejado.

## Decisão

Cada responsabilidade vive em seu próprio pacote sob `src/cesar_core/`:
`api`, `applications`, `ai`, `search`, `omniroute`, `policy`, `security`,
`telemetry`, `health`, `config`. Nenhum pacote genérico de "utilidades" é
criado. Lógica de domínio (ex.: health) fica separada da camada HTTP (`api`),
que apenas expõe rotas sobre essa lógica.

## Consequências

Novo código tem um lugar óbvio para entrar. O custo é mais arquivos pequenos
em vez de poucos arquivos grandes -- aceito conscientemente como troca por
manutenibilidade a longo prazo.
