# ADR 0017 — SearXNG e limite de saída de Search

Decisão aprovada pelo usuário na TASK-118G.

`searxng-search` é certificado para `search_type=web`, purpose `market_research`,
classes existentes sob política de custo `FREE_ONLY` (não é classe de serviço).
Sem conta/API key do SearXNG; custo reportado US$ 0. Requer serviço local.

`max_results` é limite obrigatório de resultados expostos, não de aquisição
externa. Quando existe suporte nativo, encaminhar o limite. SearXNG pode
adquirir 20/31 resultados para cap 3. OmniRoute trunca a resposta e SearchManager
do Core garante também o cap final. Não é bug nem enforcement externo.

Configuração: SearXNG com `search.formats: [html, json]`, acesso local; OmniRoute
com conexão `searxng-search` e `providerSpecificData.baseUrl` apontando para
`/search`. Core habilitado, target `searxng-search` e
`CESAR_CORE_SEARCH_PROVIDER_HEALTH_URL` para `/healthz`. Sem URL de saúde, esse
target não é considerado configurado. Dependência fora do ar degrada readiness.
Capabilities descrevem configuração, não substituem prontidão ao vivo.
Examples permanecem desabilitados; nenhuma instalação permanente nesta etapa.

Cache do OmniRoute: TTL 180s; chave inclui query/provider/tipo/cap/localidade e
opções. Vazio é sucesso e não provoca fallback. Context7 continua exclusivamente
para documentação técnica. CAPTCHA/rate limit dos motores são limitações
operacionais: resultados de mercado não garantem preço/estoque atual.

Baseline: OmniRoute 3.8.50, digest do ADR 0012. SearXNG testado com digest
`sha256:3602e6ddbeba037f5d800d1ed9d296a8b93c9f5b3cf9d05fa179d0e766dd59a1`.
