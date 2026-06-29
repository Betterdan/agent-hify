from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KbConfig(BaseModel):
    chunk_size: int = 512
    overlap: int = 50
    top_k: int = 5
    threshold: float | None = None


class KnowledgeBaseCreate(BaseModel):
    name: str
    embedding_model_id: int
    config: KbConfig = Field(default_factory=KbConfig)


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    config: KbConfig | None = None


class KnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    embedding_model_id: int
    config: dict[str, object]
    created_at: datetime
    updated_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kb_id: int
    filename: str
    status: str
    error: str | None
    char_count: int
    created_at: datetime
    updated_at: datetime


class RetrievedChunk(BaseModel):
    chunk_id: int
    kb_id: int
    content: str
    score: float
    metadata: dict[str, object] = Field(default_factory=dict)
