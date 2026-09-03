"""Contratos públicos de erro da fronteira de segurança."""

from pydantic import BaseModel, Field


class SecurityErrorDetail(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class SecurityErrorResponse(BaseModel):
    error: SecurityErrorDetail
