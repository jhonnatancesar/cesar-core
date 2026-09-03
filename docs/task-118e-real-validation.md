# TASK-118E — validação real em 2026-09-03

## Resultado final aprovado — 21/21

**TASK-118E aprovada para commit: 21 contracts reais passaram, sem falhas
ou skips, em 43,94 s.** A rodada final separou enforcement de limite e
conclusão textual; nenhuma implementação foi alterada nessa correção.

- `test_ai_adapter_real_small_cap_and_response_validation`: executa caps
  **8 e 128**, captura payload real e exige completion <= cap. Conteúdo não
  textual exige rejeição normalizada; texto válido exige normalização exata.
- `test_ai_real_text_completion_with_comfortable_cap`: positivo separado via
  `POST /v1/ai/generate`, cap **512**, HTTP 200, texto não vazio, usage e IDs.
  Esse orçamento dá margem sobre os 128 anteriormente esgotados, sem retries.
  O positivo focado consumiu 176 tokens, justificando a margem.

| Prova final | Completion tokens | Resultado |
|---|---|---|
| Cap 8 | 8 | Conteúdo nulo, rejeição fail-closed |
| Cap 128 | 98 | Texto válido normalizado, dentro do limite |
| Positivo cap 512 | 46 | HTTP 200, `CAPPED` |

Target solicitado: `oc/mimo-v2.5-free`; modelo reportado: `mimo-v2.5-free`.
O registry da imagem instalada declara `id: opencode`, `alias: oc`; portanto
é o mesmo target `opencode/mimo-v2.5-free`, sem troca de configuração.

Os dois contracts focados passaram; os 12 testes existentes do adapter,
incluindo fail-closed por usage ausente/excessivo, também passaram. Ruff e
`git diff --check` passaram. Auth, capability, quota pré-upstream, separação
AI/Search e matriz de readiness passaram novamente nos 21 contracts.

Foi usada a mesma instância temporária autenticada 3.8.50/digest descrita
abaixo. Ao final, ela foi removida; os containers originais OmniRoute/Redis
ficaram parados e `REQUIRE_API_KEY=false` foi confirmado no original.
Nenhuma mudança de PROD, 118F ou do prompt reservado.

As seções seguintes são histórico das rodadas intermediárias, incluindo
falhas que motivaram a separação dos contracts; não são bloqueios atuais.

## Histórico — rodada autenticada intermediária

**TASK-118E continua aberta: os cinco bloqueantes passaram; rodada completa
final 20 PASS / 1 FAIL, sem skips. A meta 21/21 não foi atingida.**

Nenhuma implementação foi alterada nesta rodada. Somente os dois arquivos de
contracts e este relatório foram ajustados. O baseline abaixo foi preservado
como histórico, não como descrição do ambiente temporário desta rodada.

### Classificação antes das correções

| Falha original | Classe | Evidência / causa |
|---|---|---|
| Auth AI | C — ambiente | Teste chama adapter/OmniRoute diretamente, não Core sem Bearer. `REQUIRE_API_KEY=false` aceitava token inválido; com true o mesmo teste passou sem alteração. |
| Readiness esperada ok | C — ambiente | Probes exigem rejeição de token inválido e aceitação do válido. Auth desabilitada impedia ok; o mesmo contract passou com auth habilitada. Não é degraded permanente da implementação. |
| max_tokens negativo | B — harness | Usava `auto/best-free` e pressupunha excesso de usage. A exceção efetiva era conteúdo não textual, não evidência de excesso. Substituído por cap 8 no target certificado, com captura real de payload e usage. |
| Isolamento AI | C — ambiente | Arquivo correto chegava ao wire, mas upstream aceitava chave inválida. Com auth true: AI upstream 401/Core 502; Search 200. |
| Isolamento Search | C — ambiente | Mesmo motivo. Com auth true: Search upstream 401/Core 502; AI 200. |

### Runtime e autenticação

Container temporário `omniroute-118e-auth-validation`, mesma imagem 3.8.50 e
digest `sha256:085c57adf499a8aaa9f35ccde95c0df9c11bd9ecd18d6c9edbf3b68b8079ba9d`,
mesmo bind de dados e porta loopback. Apenas `REQUIRE_API_KEY=true` diferiu
do ambiente original. O container original ficou parado e intocado.

Arquivos AI/Search distintos continham cópias da mesma chave válida real;
nenhuma chave nova foi emitida. A prova certifica seleção independente dos
arquivos e rejeição autenticada, não credenciais emitidas com scopes distintos.
As assertions de isolamento agora também exigem upstream 401 e o nome lógico
correto de cada arquivo; não basta qualquer erro 502.

Core real: sem Bearer 401, inválido 401, válido 200 com identidade `gg_oferta`.
Capability negada 403 e quota esgotada 429, ambas com zero novos requests
upstream. Quota disponível executou com sucesso. Claudião permaneceu RESERVED
sem credencial criada. Traces/IDs e métricas passaram.

Readiness com ambos ativos: válido **ok**; chave inválida ou arquivo ausente,
individualmente em AI/Search: **degraded**; ambos desabilitados: **ok**.
O harness agora exige auth gates true e estado válido ok, sem alternativa
condicional que aceite degraded nesse cenário controlado.

### max_tokens: enforcement observado e falha restante

Target `oc/mimo-v2.5-free` (alias do provider opencode), resolvido no response
como `mimo-v2.5-free`. Nenhuma certificação foi feita com big-pickle.

Payload real do contract corrigido:

```json
{"model":"oc/mimo-v2.5-free","messages":[{"role":"user","content":"Reply with exactly: CESAR_CORE_MAX_TOKENS_PROBE"}],"max_tokens":8}
```

Usage final: prompt 259, completion **8**, total 267, finish_reason `length`,
content null. Cap respeitado upstream, e adapter rejeitou conteúdo não textual.
O teste não transforma essa rejeição em geração bem-sucedida. Caso haja texto,
exige normalização exata; em qualquer caso exige completion positivo <= 8.

O contract positivo preexistente manteve prompt `Reply with exactly: CAPPED`,
cap **128**, target certificado e exigência de resposta textual `CAPPED`.
Um probe inicial retornou `CAPPED`, completion **17**. Porém, as duas rodadas
completas falharam nesse contract com conteúdo não textual. A última captura
provou prompt 253, completion **128**, total 381, finish_reason `length`,
content null. Portanto o orçamento foi esgotado sem resposta textual: não é
violação do cap nem evidência de bug de auth da 118E. É variabilidade real
do target sob o orçamento certificado. Não aumentamos cap, trocamos target,
adicionamos retry para mascarar falha ou removemos a assertion de conteúdo.

O antigo contract negativo foi renomeado para
`test_ai_adapter_real_small_cap_and_response_validation`. Não se pressupõe
mais uma violação espontânea de provider para provar defesa pós-resposta.
Os testes unitários existentes do adapter continuam comprovando fail-closed
com usage ausente, não verificável e completion 51 para cap 50. São provas
unitárias de violação induzida, explicitamente distintas da prova real de cap.

### Execuções finais e restauração

- Quatro contracts de ambiente, antes de editar harness: **4 PASS**.
- Cinco contracts bloqueantes após ajuste: **5 PASS**.
- Todos os 21 reais: **20 PASS / 1 FAIL**, repetido com captura diagnóstica.
- Única falha final: `test_ai_adapter_real_upstream_enforces_max_tokens`.
- Adapter focado: **12 PASS**, incluindo fail-closed por usage inválido/excessivo.
- Ruff e `git diff --check`: **PASS**.

Busca explícita de secrets nas respostas, logs Core, traces e métricas do
harness: zero ocorrências. Logs reais OmniRoute: **60.783 bytes**, **33 valores
distintos** pesquisados em memória, zero ocorrências; secrets não impressos.

Container temporário parado e removido após a leitura dos logs; nenhum volume
ou imagem removido. `omniroute` e `omniroute-redis` confirmados **exited**.
Original confirmado com `REQUIRE_API_KEY=false` e digest inalterado.
Sem commit, push, PROD, 118F ou alteração do prompt reservado.

Parada para revisão: falta decidir como tratar a instabilidade de conclusão
textual do target certificado sob cap 128, sem enfraquecer o contrato.

## Histórico — resultado anterior com auth desabilitada

**Continua aberta: 21 casos reais executados, 16 passaram e 5 falharam.**
Nenhuma assertion antiga foi relaxada e nenhuma implementação foi alterada
nesta rodada. A falha de ACL inicial do pytest foi contornada com um
`--basetemp` novo e execução autorizada fora do sandbox.

Instância: container existente `omniroute`, em `127.0.0.1:20128`, imagem
oficial 3.8.50, digest
`sha256:085c57adf499a8aaa9f35ccde95c0df9c11bd9ecd18d6c9edbf3b68b8079ba9d`.
Redis existente: `omniroute-redis`. Flag real preservada:
`REQUIRE_API_KEY=false`. Não houve alteração de versão, configuração ou PROD.

## Inventário dos 16 contracts anteriores

Todos pertencem a `tests/test_omniroute_contract.py` e foram executados.

| Teste | Etapa | Rodada final |
|---|---|---|
| `test_a_health_against_real_omniroute_without_any_paid_provider` | 118B | PASS |
| `test_b_search_against_real_omniroute_using_the_free_fallback_provider` | 118B | PASS |
| `test_c_chat_completions_against_real_omniroute_unresolvable_model_is_a_client_error` | 118B | PASS |
| `test_authenticated_request_against_real_omniroute` | 118B | PASS |
| `test_invalid_credential_is_a_distinct_auth_error` | 118B | PASS |
| `test_ai_adapter_normalizes_real_omniroute_client_error` | 118C | PASS |
| `test_ai_generate_endpoint_normalizes_real_omniroute_completion` | 118C/118E auth | PASS |
| `test_ai_adapter_rejects_real_provider_that_violates_max_tokens` | 118C | FAIL: conteúdo não textual, não a violação de usage esperada |
| `test_ai_adapter_real_upstream_enforces_max_tokens` | 118C | PASS final; falhou nas duas rodadas anteriores com conteúdo não textual |
| `test_ai_adapter_normalizes_real_authentication_error` | 118C/118E | FAIL: chat aceitou chave inválida |
| `test_ai_adapter_normalizes_real_timeout` | 118C | PASS |
| `test_ai_adapter_normalizes_real_connection_refusal` | 118C | PASS |
| `test_search_adapter_normalizes_real_omniroute_response_and_usage` | 118D | PASS |
| `test_search_endpoint_runs_real_policy_manager_adapter_and_gateway` | 118D/118E auth | PASS |
| `test_search_adapter_normalizes_real_provider_request_error` | 118D | PASS |
| `test_readiness_and_capabilities_with_real_enabled_ai` | 118C → 118E | FAIL: esperava ok; runtime corretamente retornou degraded |

O sucesso do teste de chave inválida em `/v1/models` não prova proteção de
chat/Search: os probes reais das duas rotas retornaram auth gate `false`.

## Cinco casos adicionais da 118E

`tests/test_security_contract.py` inicia um Core isolado em socket loopback
real. As chamadas percorrem HTTP, auth, registry, quota, manager, adapter e
OmniRoute. O observador de transporte delega para sockets reais; não simula
respostas nem providers. A restrição de capability é configuração temporária
do registry no processo de teste, restaurada ao final.

- Auth/authorization/quota AI: PASS.
- Auth/authorization/quota Search: PASS.
- Credencial AI inválida isolada: FAIL, AI=200 e Search=200.
- Credencial Search inválida isolada: FAIL, AI=200 e Search=200.
- Matriz de readiness: PASS para os estados efetivamente observados.

Sem Bearer e Bearer inválido retornaram 401; credential válida retornou 200.
O header forjado `X-Application-Id: claudiao` não mudou a identidade dos traces:
permaneceu `gg_oferta`. Claudião continua RESERVED, sem scopes e sem arquivo de
credential criado. Capability removida retornou 403 antes de qualquer request
no transporte OmniRoute. Quota=1 permitiu a primeira chamada e retornou 429
`quota_exceeded` com `Retry-After` na segunda, sem novo request upstream.

Os dois sucessos AI da rodada final tiveram upstream IDs
`7e79343b-2876-4158-a3b1-c4650ae54a7b` e
`7fb7e179-0952-4451-a0b4-bd2a2e9baa6e`. Os sucessos Search tiveram
`1e112fb5-2cc0-42c4-afe8-e2a7e21a2760` e
`f86343c2-61cf-4b5b-bcae-58cd719c5cdb`.
AI retornou `CESAR_CORE_118E_OK`; Search retornou 1–3 resultados normalizados
do target especializado Context7. O contract anterior também provou cache.

## Limite da prova de credenciais

Foi comprovado na rede que cada request usou o arquivo lógico de sua
capability, inclusive quando esse arquivo continha a chave inválida. Não houve
troca silenciosa de configuração pelo Core. **Isolamento autenticado upstream
não foi comprovado**: OmniRoute aceitou os tokens inválidos em ambas as rotas.

Havia somente uma chave OmniRoute local disponível. Os arquivos válidos do
harness são cópias dessa chave em caminhos distintos; não são duas credenciais
independentemente emitidas. Nenhuma nova chave foi provisionada no OmniRoute.
Não apresentar essa prova de seleção de arquivos como certificação de duas
credenciais reais de menor privilégio.

## Observabilidade e readiness

Request/correlation IDs foram verificados em sucesso e rejeição. Traces
confirmaram application autenticada; path identifica capability; status
identifica resultado. Métrica de HTTP 429 por `gg_oferta` aumentou. Upstream IDs
foram observados somente quando houve tráfego upstream.

O harness procurou explicitamente todos os valores de secrets usados nas
respostas HTTP, registros de transporte, campos dos logs capturados e métricas:
nenhuma ocorrência. Os logs reais do container também foram capturados em
memória e pesquisados, sem imprimir seu conteúdo ou secrets: nenhuma ocorrência.

| Estado | Readiness real |
|---|---|
| Configuração válida, AI/Search ativos | degraded |
| AI com chave inválida | degraded |
| AI com arquivo de chave ausente | degraded |
| Search com chave inválida | degraded |
| Search com arquivo de chave ausente | degraded |
| AI e Search desabilitados | ok |

Auth upstream desabilitada mascara a discriminação entre credencial válida e
inválida na readiness. A matriz não certifica o estado `ok` com gateways ativos.
A política foi preservada, não ajustada para obter verde.

## Validação final e decisão pendente

Rodada combinada: 16 PASS / 5 FAIL, sem skips. Focados: 77 PASS.
Ruff e `git diff --check`: PASS. A suíte inteira não foi repetida.

Alterações desta rodada: somente harness de contracts reais e este relatório.
Sem commit/push, sem TASK-118F, sem modificação do prompt reservado.
Falta decisão sobre configurar autenticação upstream e provisionar credenciais
independentes para certificar isolamento; também permanece a falha do contract
de violação de max_tokens e a instabilidade observada no contract do cap.
