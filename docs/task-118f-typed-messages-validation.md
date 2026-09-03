# TASK-118F — mensagens tipadas e integração DEV

Estado: aguardando revisão; sem commit/push/PROD.

Contrato legado `prompt` preservado; novo `messages` aceita somente
system/user/assistant com conteúdo textual. XOR e validação geram 400 seguro;
sem eco de input. `AIRequest` não herda o DTO e contém apenas mensagens
normalizadas. Adapter preserva ordem/roles e aplica o mesmo max_tokens.
Auth, capability, quota, policy e fail-closed não ganharam outro caminho.

OmniRoute 3.8.50/digest oficial inspecionado: `ChatCompletionRequest` em
`/app/docs/openapi.yaml` declara messages; rota real aceita esse array.
Captura de request real confirmou:

```json
{"model":"oc/mimo-v2.5-free","messages":[{"role":"system","content":"Responda exatamente com a palavra CAPPED."},{"role":"user","content":"Qual palavra você deve responder?"}],"max_tokens":512}
```

Resultado Core: `CAPPED`, modelo `mimo-v2.5-free`, usage prompt 29,
completion 33, total 62. O texto sozinho não foi usado como prova de roles:
a captura do payload delegado ao transporte de rede confirmou a sequência.

- Core: **22/22 contracts reais**, sendo 21 anteriores e 1 novo de roles.
- Regressão não-contract: **204 PASS**.
- GG Oferta: **122 testes focados PASS** e contract real permanente **1 PASS**.
- Fluxo real incluiu factory/manager e CesarCoreAIProvider do GG Oferta,
  HTTP loopback Core e OmniRoute; correlação e resposta CAPPED confirmadas.
- Core encerrado: erro tipado de conexão no consumidor, sem fallback default.
- Logs/traces/métricas capturados pesquisados em memória: sem os segredos ou
  conteúdo das mensagens. Credencial DEV em dois arquivos distintos ignorados,
  sem reutilizar a chave do OmniRoute. Não registrar valores no relatório.
- Ruff/diff-check PASS; nenhum typechecker estático configurado.

As flags do consumidor permanecem false por padrão. Grounding conserva a
rota anterior e 118G não foi iniciada. `.env` global do Core não foi criado:
configuração de teste por variáveis de processo evita `extra_forbidden` entre
Settings de namespaces distintos, limitação preexistente registrada.
