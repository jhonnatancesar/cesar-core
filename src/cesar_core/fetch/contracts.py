"""Contrato neutro do Central Web Fetch/Enrichment Gateway do César Core.

Sem payload específico de provider: o adapter concreto traduz este contrato
para o OmniRoute (``POST /v1/web/fetch``) e normaliza a resposta de volta
para o domínio Fetch. Mesmo formato de duas camadas do Search/AI (ver ADR
0010): ``FetchRequestPayload`` é o DTO HTTP público -- nunca carrega
identidade do chamador; ``FetchRequest`` é a requisição interna de domínio,
construída pelo César Core combinando o ``ApplicationContext`` confiável com
um ``FetchRequestPayload`` já validado.

Fetch é enriquecimento de UMA URL já conhecida pelo chamador (Search
encontra URLs; Fetch extrai conteúdo delas) -- não é uma segunda busca, não
recebe query nem parâmetros de negócio do GG Oferta.
"""

import ipaddress
import socket
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cesar_core.applications.context import ApplicationContext
from cesar_core.policy.requirements import Requirements

_ALLOWED_PORTS = {80, 443}

# Parâmetros de ALTA CONFIANÇA na query string -- mesmo critério do GG Oferta
# (`app/search/url_safety.py`, FASE E.3), reimplementado aqui como segunda
# camada independente: o Core não confia que todo chamador (hoje só GG
# Oferta, mas a fronteira HTTP não garante isso para sempre) já filtrou sua
# própria URL. Deliberadamente SEM termos genéricos de e-commerce (id, sku,
# product, ref, page, category, code, key) -- mesma decisão do GG, para não
# recusar URL legítima de loja por falso positivo.
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "refresh_token",
        "oauth_token",
        "api_key",
        "apikey",
        "api-key",
        "authorization",
        "password",
        "passwd",
        "session",
        "session_id",
        "jwt",
    }
)

# URLs assinadas de provedores de nuvem -- a assinatura já É o segredo.
_CLOUD_SIGNATURE_QUERY_KEYS = frozenset(
    {
        "x-amz-signature",
        "x-amz-credential",
        "x-amz-security-token",
        "x-goog-signature",
        "x-goog-credential",
    }
)

# Azure SAS não tem um nome de parâmetro único -- é a combinação de `sig`
# (assinatura) com `sv` (service version).
_AZURE_SAS_MARKERS = frozenset({"sig", "sv"})


def strip_url_fragment(url: str) -> str:
    """Remove o ``#fragment`` de ``url``, se houver.

    Puramente sintático (sem I/O) -- por isso vive dentro do
    ``field_validator`` de ``url``, ao contrário de ``reject_ssrf_target``.
    Um fragment nunca é enviado pela rede pelo cliente HTTP real (é
    semântica pura de user-agent), mas o valor bruto do campo ``url`` deste
    contrato é o que efetivamente é logado/propagado internamente (Core,
    OmniRoute) antes de qualquer requisição HTTP acontecer -- por isso é
    removido aqui, o mais cedo possível, e não apenas confiado ao
    comportamento do cliente HTTP final.
    """
    parsed = urlsplit(url)
    if not parsed.fragment:
        return url
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def reject_sensitive_query_target(url: str) -> None:
    """Recusa ``url`` se a query string carregar um parâmetro de alta
    confiança (token, credencial, senha, sessão) ou uma URL assinada de
    nuvem conhecida (AWS SigV4, GCS, Azure SAS).

    Deliberadamente SEPARADA de ``reject_ssrf_target``: SSRF é sobre PRA
    ONDE a URL aponta na rede; isto aqui é sobre O QUE a URL carrega como
    dado -- duas categorias de risco distintas, nunca combinadas numa só
    função. A ação aqui é sempre rejeitar a URL inteira, nunca mascarar o
    valor sensível e prosseguir: mascarar produziria uma URL inválida (o
    provider não conseguiria buscar a página real) e esconderia o
    problema em vez de reportá-lo.
    """
    keys = frozenset(
        key.lower() for key, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True)
    )
    if keys & _SENSITIVE_QUERY_KEYS:
        raise ValueError("url query must not contain sensitive credentials or tokens")
    if keys & _CLOUD_SIGNATURE_QUERY_KEYS:
        raise ValueError("url query must not contain a cloud-signed request")
    if _AZURE_SAS_MARKERS.issubset(keys):
        raise ValueError("url query must not contain an Azure SAS signature")


def _is_blocked_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def reject_ssrf_target(url: str) -> None:
    """Bloqueia alvos internos/privados antes de qualquer chamada upstream.

    Defesa em profundidade contra SSRF: ``url`` chega de um chamador
    autenticado (``gg_oferta``), mas nada impede um valor manipulado (ex.:
    um resultado de busca malicioso) de apontar pra infraestrutura interna
    (loopback, RFC1918, link-local/metadata de nuvem 169.254.0.0/16, etc.).
    Isto NÃO é garantia completa: quem executa o fetch de verdade é o
    provider abaixo do OmniRoute (Firecrawl e afins, tipicamente rede
    diferente da nossa), e DNS rebinding pode trocar o IP entre esta
    validação e a resolução real feita por esse provider -- proteção
    definitiva contra isso pertence à camada que executa o fetch, fora
    deste repositório. Aqui barra o caso comum (payload aponta a um
    IP/host interno óbvio) o mais cedo possível.

    Deliberadamente FORA do ``field_validator`` do modelo: resolver DNS é
    I/O de rede, e ``FetchRequestPayload``/``FetchRequest`` continuam
    construíveis em memória (testes, chamadas internas) sem depender de
    rede/DNS disponível. A rota HTTP (``api/routes/fetch.py``, único ponto
    de entrada externo desta capability) chama esta função explicitamente
    antes de repassar a requisição ao ``FetchManager``.
    """
    parsed = urlsplit(url)
    if parsed.username or parsed.password:
        raise ValueError("url must not contain userinfo credentials")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("url must have a resolvable host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in _ALLOWED_PORTS:
        raise ValueError("url port must be 80 or 443")
    hostname = hostname.rstrip(".").lower()
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError):
        raise ValueError("url host could not be resolved") from None
    for info in infos:
        raw_ip = info[4][0]
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            raise ValueError("url host resolved to an invalid address") from None
        if _is_blocked_address(ip):
            raise ValueError(
                "url must not target internal or private network addresses"
            )


class FetchRequestPayload(BaseModel):
    """DTO HTTP público de uma requisição de enriquecimento de URL.

    Não recebe ``application_id`` nem qualquer outro dado de identidade no
    corpo: quem está chamando é sempre resolvido pelo Core, nunca declarado
    pelo cliente dentro do payload. Não recebe nome de provider nem opção
    específica de provider (formato, profundidade, seletor): esta é a
    fronteira provider-neutral -- o adapter concreto decide isso.
    """

    model_config = ConfigDict(extra="forbid")

    requirements: Requirements
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        value = value.strip()
        if not value or not (
            value.startswith("http://") or value.startswith("https://")
        ):
            raise ValueError("url must be an absolute http(s) URL")
        reject_sensitive_query_target(value)
        return strip_url_fragment(value)


class FetchRequest(FetchRequestPayload):
    """Requisição interna de domínio: contexto confiável + payload.

    Só o César Core cria esta instância, depois de resolver
    ``ApplicationContext`` -- nunca é deserializada diretamente do corpo de
    uma requisição HTTP.
    """

    context: ApplicationContext


class FetchUsage(BaseModel):
    """Uso normalizado do enriquecimento informado pelo gateway upstream."""

    fetch_cost_usd: float = Field(default=0.0, ge=0)


class FetchResponse(BaseModel):
    """Forma neutra de uma resposta de enriquecimento devolvida pelo Core.

    ``fetched=False`` é sucesso de negócio, não erro: a URL foi alcançada
    pelo provider, mas a origem específica não devolveu conteúdo aproveitável
    (bloqueio/paywall/página vazia). O chamador nunca recebe uma exceção
    nesse caso -- mesma semântica que ``FirecrawlScrapeProvider.scrape_basic``
    já tinha no GG Oferta antes desta capability existir no Core.
    """

    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    provider_gateway: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    url: str = Field(min_length=1)
    fetched: bool
    title: str | None = None
    content: str | None = None
    truncated: bool = False
    usage: FetchUsage = Field(default_factory=FetchUsage)
    latency_ms: float = Field(ge=0)
    upstream_request_id: str | None = None


class FetchErrorDetail(BaseModel):
    """Detalhe de erro estável do endpoint Fetch."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    upstream_request_id: str | None = None


class FetchErrorResponse(BaseModel):
    """Envelope público de erro do Central Web Fetch/Enrichment Gateway."""

    error: FetchErrorDetail
