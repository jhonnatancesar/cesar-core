# ADR 0015 -- Central Web Search Gateway sobre o transporte OmniRoute

## Status

Aceito (TASK-118D, primeira fatia vertical).

Atualização 118G: ADR 0017 certifica SearXNG em DEV e formaliza `max_results`
como limite obrigatório de saída. As descrições abaixo de falta de provider
geral representam o estado histórico da 118D. A configuração permanente
continua desligada, sem deploy de SearXNG.

## Contexto

A TASK-118B entregou o transporte HTTP para `/v1/search`, mas não podia
definir o contrato público, selecionar provider nem aplicar policy de negócio.
Expor o payload nativo do OmniRoute acoplaria consumidores ao gateway e
permitiria que escolhessem provider fora da policy central.

## Decisão

- O contrato público é `POST /v1/search`, com `SearchRequestPayload` no body e
  `ApplicationContext` resolvido separadamente.
- O DTO público contém `query`, `max_results` e `Requirements`; não aceita
  application, purpose, provider ou IDs de tracing no body.
- `SearchPolicy` resolve `(application_id, purpose, service_class)` para um
  `SearchProviderTarget`. Purpose `*` é fallback de regra de policy.
- `FREE_ONLY` bloqueia providers marcados como pagos. `max_results` respeita o
  teto do alvo e é rejeitado antes de qualquer consumo upstream.
- `SearchManager` aplica policy e mede a latência total.
- `OmniRouteSearchProvider` traduz para `query`, `provider`, `search_type=web`
  e `max_results`; valida que a query ecoada é a solicitada; e normaliza
  resultados, provider, usage, cache, total disponível, falhas parciais e o
  request ID do OmniRoute.
- Usage ausente ou inválido e envelopes incompatíveis falham fechados. Uma
  lista de resultados vazia é sucesso válido.

## Semântica de fallback

O César Core faz uma chamada por requisição e não repete uma busca só porque o
resultado é vazio. Roteamento, retry e failover entre credenciais/providers
continuam pertencendo ao OmniRoute. O provider efetivamente devolvido é
comparado ao alvo da policy; se for diferente, a resposta normalizada marca
`fallback_used=true`. Erros de autenticação, request, timeout e
indisponibilidade são normalizados e não disparam cascata local silenciosa.

A configuração inicial envia provider explícito. Isso torna `FREE_ONLY`
auditável e evita que o catálogo dinâmico do OmniRoute selecione futuramente
um alvo pago sem conhecimento da policy do César Core.

## Configuração, health e capabilities

`SearchConfig` usa o prefixo `CESAR_CORE_SEARCH_`. Search permanece desligado
por padrão. Para busca Web geral, `DEFAULT_PROVIDER` atende todas as classes e
os overrides `ECONOMY_PROVIDER`, `STANDARD_PROVIDER` e `QUALITY_PROVIDER` são
opcionais. Nenhum deles é preenchido no exemplo atual: não há provider FREE
anônimo funcional comprovado para busca Web geral neste ambiente.

`TECHNICAL_DOCUMENTATION_PROVIDER=context7` cria uma regra exata para o
purpose já existente `technical_documentation`. Context7 é gratuito, anônimo e
funcional, mas seu corpus especializado em documentação de bibliotecas não é
semanticamente equivalente a Web Search geral. A configuração inicial registra
somente GG Oferta; Claudião permanece reservado.

Quando qualquer target Search está configurado, `/v1/capabilities` anuncia
`search` e `omniroute` como `available`, e detalha separadamente
`search_general_web` e `search_technical_documentation`. Assim, o target
especializado não anuncia cobertura geral. `/ready` exige health do OmniRoute e prova que
`/v1/search` rejeita uma credencial inválida. O probe usa um provider
inexistente, portanto não executa busca externa caso o auth gate esteja
desabilitado. Um runtime com `REQUIRE_API_KEY=false` fica corretamente
`degraded` para Search.

## Validação real

Os contract tests usam o baseline pinado `diegosouzapw/omniroute:3.8.50`
(digest no ADR 0012). Eles capturam o JSON efetivamente enviado pelo adapter,
executam o provider gratuito `context7` e comprovam a cadeia rota -> contexto ->
policy -> manager -> adapter -> OmniRoute, incluindo resultados reais, usage,
cache, correlation/request IDs e limite de resultados, sempre sob o purpose
`technical_documentation`; não comprovam Web Search geral. `duckduckgo-free`
permanece no catálogo/fallback upstream, mas neste ambiente o DuckDuckGo Lite
responde com uma página anti-bot HTTP 202, que o OmniRoute 3.8.50 representa
como resultado vazio. SearXNG e Ollama Search exigem configuração externa e
não são anunciados como operacionais. O Market Research do GG Oferta não é
migrado nesta TASK.

## Consequências

Consumidores dependem de um contrato neutro e não escolhem providers. AI e
Search continuam com managers, policies, contratos e adapters próprios. A
migração do GG Oferta e seu fallback direto para Firecrawl permanecem fora do
escopo, reservados à TASK-118G.
