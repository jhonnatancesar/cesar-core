"""Contrato neutro do Central Web Search Gateway do César Core.

Sem payload específico de provider: o adapter concreto traduz este contrato
para o OmniRoute e normaliza a resposta de volta para o domínio Search.

Duas camadas (ver ADR 0010): ``SearchRequestPayload`` é o DTO HTTP
público -- nunca carrega identidade do chamador, só o payload funcional
e os requirements. ``SearchRequest`` é a requisição interna de domínio:
o César Core a constrói combinando o ``ApplicationContext`` confiável
(resolvido por ``api/deps.py``, e futuramente por autenticação real na
TASK-118E) com um ``SearchRequestPayload`` já validado.
"""

from pydantic import BaseModel, Field, field_validator

from cesar_core.applications.context import ApplicationContext
from cesar_core.policy.requirements import Requirements


class SearchRequestPayload(BaseModel):
    """DTO HTTP público de uma requisição de busca.

    Não recebe ``application_id`` nem qualquer outro dado de identidade
    no corpo: quem está chamando é sempre resolvido pelo Core, nunca
    declarado pelo cliente dentro do payload.
    """

    requirements: Requirements
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query cannot be blank")
        return value


class SearchRequest(SearchRequestPayload):
    """Requisição interna de domínio: contexto confiável + payload.

    Só o César Core cria esta instância, depois de resolver
    ``ApplicationContext`` -- nunca é deserializada diretamente do corpo
    de uma requisição HTTP.
    """

    context: ApplicationContext


class SearchResult(BaseModel):
    """Um resultado individual de busca."""

    title: str
    url: str
    snippet: str = ""
    position: int | None = Field(default=None, ge=1)
    score: float | None = Field(default=None, ge=0)
    published_at: str | None = None


class SearchUsage(BaseModel):
    """Uso normalizado da busca informado pelo gateway upstream."""

    queries_used: int = Field(ge=0)
    search_cost_usd: float = Field(ge=0)
    llm_tokens: int | None = Field(default=None, ge=0)


class SearchUpstreamIssue(BaseModel):
    """Falha parcial reportada pelo upstream sem invalidar a resposta."""

    provider: str
    code: str
    message: str


class SearchResponse(BaseModel):
    """Forma neutra de uma resposta de busca devolvida pelo César Core."""

    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    results: list[SearchResult] = Field(default_factory=list)
    provider_gateway: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    usage: SearchUsage
    latency_ms: float = Field(ge=0)
    total_results_available: int | None = Field(default=None, ge=0)
    cached: bool = False
    fallback_used: bool = False
    upstream_request_id: str | None = None
    upstream_issues: list[SearchUpstreamIssue] = Field(default_factory=list)


class SearchErrorDetail(BaseModel):
    """Detalhe de erro estável do endpoint Search."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    upstream_request_id: str | None = None


class SearchErrorResponse(BaseModel):
    """Envelope público de erro do Central Web Search Gateway."""

    error: SearchErrorDetail
