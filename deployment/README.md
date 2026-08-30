# Topologia de deployment (futura -- não aplicada nesta fase)

Esta pasta documenta a topologia pretendida para quando o César Core for
implantado de fato. Nada aqui é executado ou aplicado na TASK-118A: nenhum
Docker de PROD é alterado, nenhum deployment é criado.

## Topologia conceitual

```text
containers do GG Oferta
   -> rede Docker externa "cesar-platform"
   -> César Core
```

- O `collection_worker` Windows acessa o César Core apenas via loopback:
  a porta do César Core é publicada **somente** em `127.0.0.1`, nunca em
  `0.0.0.0`.
- Não há hostname público nem Cloudflare para o César Core nesta fase.

Exemplo conceitual de publicação de porta (host:core), apenas ilustrativo:

```text
127.0.0.1:<porta-host>:<porta-core>
```

Ver `deployment/docker-compose.example.yml` para a forma conceitual dessa
topologia. Esse arquivo não é usado por nenhum ambiente real ainda.
