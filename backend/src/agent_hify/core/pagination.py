from __future__ import annotations

import base64
import json
from datetime import datetime

from pydantic import BaseModel


class CursorPage[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False


class OffsetPage[T](BaseModel):
    items: list[T]
    total: int | None = None
    page: int = 1
    page_size: int = 20


def encode_cursor(created_at: datetime, id: int) -> str:
    raw = json.dumps([created_at.isoformat(), id]).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
    ts_str, id_ = json.loads(raw)
    return datetime.fromisoformat(ts_str), int(id_)
