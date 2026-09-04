"""DTOs estritos da API administrativa."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=1024)


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,62}$")
    display_name: str = Field(min_length=1, max_length=100)
    client_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,100}$")


class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=100)
    state: Literal["active", "disabled"]
    capabilities: set[Literal["ai", "search"]]
    quotas: dict[Literal["ai", "search"], PositiveInt]


class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,62}$")
    name: str = Field(min_length=1, max_length=100)
