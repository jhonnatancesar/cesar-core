# Topologia de deployment pretendida

Esta pasta documenta a topologia pretendida para quando o César Core for
implantado. O projeto atual não contém `Dockerfile`, pipeline de publicação
nem configuração de produção; portanto, o compose é somente uma referência
de rede e portas, não um artefato executável completo.

## Topologia conceitual

```text
containers do GG Oferta
   -> rede Docker externa "cesar-platform"
   -> César Core
```

- O `collection_worker` Windows acessa o César Core apenas via loopback:
  a porta do César Core é publicada **somente** em `127.0.0.1`, nunca em
  `0.0.0.0`.
- Não há hostname público nem configuração de Cloudflare neste repositório.

Exemplo conceitual de publicação de porta (host:core), apenas ilustrativo:

```text
127.0.0.1:<porta-host>:<porta-core>
```

Ver `deployment/docker-compose.example.yml` para a forma conceitual dessa
topologia. Antes de usá-lo será necessário adicionar uma imagem ou
`Dockerfile`, configurar a rede externa e fornecer o arquivo `.env` e o
secret do OmniRoute no ambiente de destino.
