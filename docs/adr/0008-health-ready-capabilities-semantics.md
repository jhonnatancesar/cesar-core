# ADR 0008 -- Semântica exata de /health, /ready e /v1/capabilities

## Status

Aceito (TASK-118A, ajuste de fundação pós-aprovação estrutural).

## Contexto

Os três endpoints podem parecer redundantes (todos retornam "tudo
not_configured, mas ok"), e é preciso deixar explícito que não são a
mesma coisa -- para que não virem checagens equivalentes por acidente
quando capacidades reais forem habilitadas.

## Decisão

- **`GET /health`** -- o processo César Core está vivo. Não checa
  nenhuma dependência, capacidade ou dado.
- **`GET /ready`** -- o César Core está apto a atender as capacidades
  que estão **atualmente configuradas/habilitadas**. Não é "tudo que um
  dia poderá existir está funcionando". Uma capacidade `NOT_CONFIGURED`
  nunca bloqueia readiness, porque ela ainda não foi habilitada e não
  impõe dependência obrigatória nenhuma.
- **`GET /v1/capabilities`** -- inventário: quais capacidades existem e
  qual o estado de cada uma. Não é um gate de prontidão; é informação.

No estado atual, inclusive após a TASK-118B, o Core está `READY` com
`ai`/`search`/`omniroute` todos `NOT_CONFIGURED`. O client de transporte
existir não habilita sozinho uma capacidade: ainda não há adapters de domínio
nem rotas públicas de AI/Search e, portanto, não há dependência obrigatória
de runtime para readiness.

Quando uma capacidade for habilitada, `get_readiness()`
passa a refletir **somente** as dependências obrigatórias das
capacidades habilitadas. Nunca reportar `ready=ok` para uma capacidade
habilitada cuja dependência obrigatória esteja quebrada -- isso seria
fake readiness positivo, exatamente o que esta TASK proíbe.

## Consequências

`health/service.py::get_readiness()` deriva seu resultado de
`get_capabilities()` (não de um valor hardcoded independente), para que
a regra acima fique estruturalmente amarrada no código, não apenas
documentada. Quando uma capacidade passar a `AVAILABLE`, quem implementar
essa mudança é obrigado a decidir a checagem de dependência real -- o
código já force esse ponto de decisão em vez de deixar passar em
silêncio.
