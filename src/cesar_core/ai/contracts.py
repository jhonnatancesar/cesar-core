"""Contrato neutro de AI Gateway do César Core.

Sem provider/model específico: este módulo define apenas o contrato de
domínio. O transporte real já existe em ``omniroute/``; o adapter concreto
que ligará esse transporte a AI deverá viver em ``ai/providers/``, nunca
neste módulo.

Duas camadas (ver ADR 0010): ``AIRequestPayload`` é o DTO HTTP público
-- nunca carrega identidade do chamador, só o payload funcional e os
requirements. ``AIRequest`` é a requisição interna de domínio: o César
Core a constrói combinando o ``ApplicationContext`` confiável (resolvido
por autenticação em ``api/deps.py``)
com um ``AIRequestPayload`` já validado. ``POST /v1/ai/generate`` executa esse
fluxo sem aceitar identidade no body.
"""

from pydantic import BaseModel, Field

from cesar_core.applications.context import ApplicationContext
from cesar_core.policy.requirements import Requirements


class AIRequestPayload(BaseModel):
    """DTO HTTP público de uma requisição de AI.

    Não recebe ``application_id`` nem qualquer outro dado de identidade
    no corpo: quem está chamando é sempre resolvido pelo Core, nunca
    declarado pelo cliente dentro do payload.
    """

    requirements: Requirements
    prompt: str = Field(min_length=1)
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Hard completion-token ceiling. César Core rejects a response when the "
            "upstream usage proves that this ceiling was exceeded."
        ),
    )


class AIRequest(AIRequestPayload):
    """Requisição interna de domínio: contexto confiável + payload.

    Só o César Core cria esta instância, depois de resolver
    ``ApplicationContext`` -- nunca é deserializada diretamente do corpo
    de uma requisição HTTP.
    """

    context: ApplicationContext


class AIUsage(BaseModel):
    """Uso de tokens normalizado, quando informado pelo upstream."""

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class AIResponse(BaseModel):
    """Resposta neutra de AI devolvida pelo César Core."""

    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    content: str
    provider_gateway: str = Field(min_length=1)
    provider: str | None = None
    model: str = Field(min_length=1)
    usage: AIUsage | None = None
    latency_ms: float = Field(ge=0)
    fallback_used: bool = False
    upstream_request_id: str | None = None


class AIErrorDetail(BaseModel):
    """Detalhe de erro estável do endpoint AI."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    upstream_request_id: str | None = None


class AIErrorResponse(BaseModel):
    """Envelope público de erro do Central AI Gateway."""

    error: AIErrorDetail
