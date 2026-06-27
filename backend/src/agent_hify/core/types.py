from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageSource(BaseModel):
    kind: Literal["url", "base64"]
    url: str | None = None
    data: str | None = None
    media_type: str | None = None


class ImageBlock(BaseModel):
    type: Literal["image"] = "image"
    source: ImageSource


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, object] = Field(default_factory=dict)


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: list[ContentBlock] = Field(default_factory=list)


ContentBlock = Annotated[
    TextBlock | ImageBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="type"),
]

# Rebuild after ContentBlock is defined so the forward reference in
# ToolResultBlock.content resolves correctly at runtime.
ToolResultBlock.model_rebuild()

_blocks_adapter: TypeAdapter[list[ContentBlock]] = TypeAdapter(list[ContentBlock])


def parse_content_blocks(raw: list[dict[str, object]]) -> list[ContentBlock]:
    return _blocks_adapter.validate_python(raw)
