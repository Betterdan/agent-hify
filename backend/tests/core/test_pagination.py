from __future__ import annotations

from datetime import UTC, datetime

from agent_hify.core.pagination import (
    CursorPage,
    OffsetPage,
    decode_cursor,
    encode_cursor,
)


def test_cursor_roundtrip() -> None:
    ts = datetime(2026, 6, 27, 10, 0, tzinfo=UTC)
    cur = encode_cursor(ts, 42)
    got_ts, got_id = decode_cursor(cur)
    assert got_ts == ts
    assert got_id == 42


def test_cursor_page_shape() -> None:
    page: CursorPage[int] = CursorPage(items=[1, 2], next_cursor="abc", has_more=True)
    assert page.has_more is True


def test_offset_page_total_optional() -> None:
    page: OffsetPage[int] = OffsetPage(items=[1], total=None, page=2, page_size=20)
    assert page.total is None
