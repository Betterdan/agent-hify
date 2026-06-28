from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderType = Literal["openai", "anthropic", "ollama", "openai_compatible"]
ModelType = Literal["llm", "embedding", "rerank"]


class ProviderIn(BaseModel):
    type: ProviderType
    name: str
    base_url: str | None = None
    credentials: dict[str, str] = Field(default_factory=dict)


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    name: str
    base_url: str | None
    enabled: bool


class ModelIn(BaseModel):
    provider_id: int
    model_key: str
    type: ModelType
    capabilities: list[str] = Field(default_factory=list)
    embedding_dim: int | None = None
    default_params: dict[str, object] = Field(default_factory=dict)


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider_id: int
    model_key: str
    type: str
    capabilities: list[str]
    embedding_dim: int | None
    enabled: bool


class ChatMessage(BaseModel):
    role: str
    content: str


class InvokeResult(BaseModel):
    content: str
    tokens_in: int
    tokens_out: int
    cost: float
    finish_reason: str


class ConnectivityResult(BaseModel):
    ok: bool
    error: str | None = None
