from __future__ import annotations

from agent_hify.core.types import parse_content_blocks


def test_parse_text_and_image_blocks() -> None:
    raw = [
        {"type": "text", "text": "hi"},
        {"type": "image", "source": {"kind": "url", "url": "http://x/y.png"}},
    ]
    blocks = parse_content_blocks(raw)
    assert blocks[0].type == "text"
    assert blocks[1].type == "image"
    assert blocks[1].source.url == "http://x/y.png"
