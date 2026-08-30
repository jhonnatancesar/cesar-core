# ADR 0006 -- Fronteira de responsabilidade entre César Core e OmniRoute

## Status

Aceito (TASK-118A).

## Contexto

É preciso deixar claro o que vive no César Core e o que vive no OmniRoute,
para que a integração futura (fora desta TASK) não borre essa fronteira.

## Decisão

O César Core possui: identidade de aplicação, política (service class,
cost policy, requirements), contratos neutros de AI/Search, health/ready/
capabilities, telemetria (correlation ID) e a fronteira (`omniroute/`) que
uma implementação futura deve respeitar. O OmniRoute possui: toda chamada
HTTP real a `/api/v1/chat/completions`, `/api/v1/search` etc., e toda
configuração de provider (Gemini/Groq/OpenRouter). Nesta TASK, `omniroute/`
contém apenas um `Protocol` (`OmniRouteGateway`) sem implementação
concreta -- nenhuma chamada de rede é feita por este repositório.

## Consequências

Quando o OmniRoute for integrado de fato, sua implementação concreta
satisfaz o `Protocol` já definido aqui, sem exigir mudança nos contratos de
AI/Search ou no registry de aplicações.
