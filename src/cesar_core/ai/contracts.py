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

``ai_profile`` é a única exceção deliberada à regra "nada de identidade
no body": o Core autentica a aplicação inteira (ex.: GG Oferta), não o
usuário final por trás de uma chamada específica, então só a aplicação
chamadora sabe se aquela chamada é de um usuário final ou de um fluxo
ADMIN/DEV. Não é ``Requirements`` (não é qualidade/custo) nem
``ApplicationContext`` (não é resolvido por autenticação) -- ver
``policy/ai_profile.py``.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cesar_core.applications.context import ApplicationContext
from cesar_core.policy.ai_profile import AIProfile
from cesar_core.policy.requirements import Requirements


class AIMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AIMessage(BaseModel):
    """Mensagem textual de domínio; independente do envelope HTTP."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    role: AIMessageRole
    content: str = Field(strict=True, min_length=1)


class AIRequestPayload(BaseModel):
    """DTO HTTP público de uma requisição de AI.

    Não recebe ``application_id`` nem qualquer outro dado de identidade
    no corpo: quem está chamando é sempre resolvido pelo Core, nunca
    declarado pelo cliente dentro do payload.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "oneOf": [{"required": ["prompt"]}, {"required": ["messages"]}],
        }
    )

    ai_profile: AIProfile
    requirements: Requirements
    prompt: str | None = Field(default=None, min_length=1)
    messages: list[AIMessage] | None = Field(default=None, min_length=1)
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Hard completion-token ceiling. César Core rejects a response when the "
            "upstream usage proves that this ceiling was exceeded."
        ),
    )
    require_search_grounding: bool = Field(
        default=False,
        strict=True,
        description="Require provider-agnostic Web grounding through OmniRoute.",
    )

    @model_validator(mode="before")
    @classmethod
    def exactly_one_input(cls, value):
        if isinstance(value, dict) and (("prompt" in value) == ("messages" in value)):
            raise ValueError("Provide exactly one of prompt or messages")
        return value

    @model_validator(mode="after")
    def require_input(self):
        if self.prompt is None and self.messages is None:
            raise ValueError("Provide exactly one of prompt or messages")
        return self

    @field_validator("messages")
    @classmethod
    def require_text_content(cls, messages):
        if messages is not None and any(not item.content.strip() for item in messages):
            raise ValueError("Message content must not be blank")
        return messages

    def to_domain(self, context: ApplicationContext) -> "AIRequest":
        messages = self.messages
        if messages is None:
            assert self.prompt is not None
            messages = [AIMessage(role=AIMessageRole.USER, content=self.prompt)]
        return AIRequest(
            context=context,
            ai_profile=self.ai_profile,
            requirements=self.requirements,
            messages=tuple(messages),
            max_tokens=self.max_tokens,
            require_search_grounding=self.require_search_grounding,
        )


class AIRequest(BaseModel):
    """Requisição interna de domínio: contexto confiável + payload.

    Só o César Core cria esta instância, depois de resolver
    ``ApplicationContext`` -- nunca é deserializada diretamente do corpo
    de uma requisição HTTP.
    """

    context: ApplicationContext
    ai_profile: AIProfile
    requirements: Requirements
    messages: tuple[AIMessage, ...] = Field(min_length=1)
    max_tokens: int | None = Field(default=None, ge=1)
    require_search_grounding: bool = Field(default=False, strict=True)


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
    grounding_requested: bool = Field(default=False, strict=True)
    grounding_performed: bool = Field(default=False, strict=True)
    grounding_sources: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_grounding_evidence(self):
        if self.grounding_performed and not self.grounding_requested:
            raise ValueError("grounding_performed requires grounding_requested")
        if self.grounding_sources and not self.grounding_performed:
            raise ValueError("grounding_sources require grounding_performed")
        if any(not source.strip() for source in self.grounding_sources):
            raise ValueError("grounding_sources must not contain blank values")
        return self


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
