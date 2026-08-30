# ADR 0006 -- Fronteira de responsabilidade entre César Core e OmniRoute

## Status

Aceito (TASK-118A). **Revisado** na mesma TASK-118A, antes do primeiro
push: a versão original desta decisão colocava um único `Protocol`
(`OmniRouteGateway`) misturando AI e Search sob `omniroute/`. Isso
estabelecia, cedo demais, uma abstração unificada indevida. A seção
"Decisão" abaixo já reflete a versão corrigida; a "Decisão original"
fica registrada por transparência.

**Atualização (TASK-118B)**: o item "Numa TASK futura (118B+)..." abaixo
já se concretizou -- `OmniRouteClient` (transporte de baixo nível para
health/chat completions/search) existe de verdade, ver ADR 0011/0012/0013.

## Nota de escopo (TASK-118B): quem é dona de que

Confusão a evitar: **118B é dona do transporte HTTP de baixo nível para
chat e search** (`OmniRouteClient.chat_completions()`/`search()` --
endpoint, auth, timeout, serialização, erro). **118C/118D são donas do
adapter de domínio** que monta o payload de negócio (qual modelo, qual
provider, política de custo) e implementa `AIProvider`/`SearchProvider`
usando esse transporte por baixo. Não confundir "118C é dona de chat"
com "118B não implementa transporte de chat" -- são coisas diferentes.

## Contexto

É preciso deixar claro o que vive no César Core e o que vive no OmniRoute,
para que a integração futura (fora desta TASK) não borre essa fronteira
-- e, dentro do próprio César Core, que AI e Search não compartilhem uma
abstração que deveriam ter separada.

## Decisão

- **`ai/`** possui contrato próprio (`ai/contracts.py`) e boundary de
  provider próprio (`ai/provider.py`, `Protocol AIProvider`).
- **`search/`** possui contrato próprio (`search/contracts.py`) e
  boundary de provider próprio (`search/provider.py`, `Protocol
  SearchProvider`).
- **`omniroute/`** é reservado para o transporte/client/config/models/
  erros de baixo nível do OmniRoute -- nunca uma abstração que una AI e
  Search. Nesta TASK, `omniroute/` não contém nenhum `Protocol`: é só o
  pacote reservado, com um docstring explicando seu papel futuro.
- Numa TASK futura (118B+), `omniroute/` ganha um `OmniRouteClient` de
  baixo nível que conhece os endpoints HTTP reais (`/api/v1/chat/
  completions`, `/api/v1/search` etc.) e toda configuração de provider
  (Gemini/Groq/OpenRouter). AI e Search consomem esse client através de
  adapters próprios -- `ai/providers/omniroute.py` implementando
  `AIProvider`, `search/providers/omniroute.py` implementando
  `SearchProvider` -- nunca diretamente, e nunca através de uma
  interface comum aos dois domínios.
- O César Core, além disso, possui: identidade de aplicação, política
  (service class, cost policy, requirements), health/ready/capabilities
  e telemetria (correlation ID, request ID).

## Consequências

Quando o OmniRoute for integrado de fato, sua implementação concreta
entra como dois adapters separados (um por domínio), cada um satisfazendo
o `Protocol` do seu próprio domínio -- sem exigir mudança nos contratos
de AI/Search ou no registry de aplicações, e sem criar uma dependência
cruzada entre `ai/` e `search/`.

## Decisão original (substituída)

> O César Core possui: identidade de aplicação, política (service class,
> cost policy, requirements), contratos neutros de AI/Search, health/ready/
> capabilities, telemetria (correlation ID) e a fronteira (`omniroute/`) que
> uma implementação futura deve respeitar. O OmniRoute possui: toda chamada
> HTTP real a `/api/v1/chat/completions`, `/api/v1/search` etc., e toda
> configuração de provider (Gemini/Groq/OpenRouter). Nesta TASK, `omniroute/`
> contém apenas um `Protocol` (`OmniRouteGateway`) sem implementação
> concreta -- nenhuma chamada de rede é feita por este repositório.
