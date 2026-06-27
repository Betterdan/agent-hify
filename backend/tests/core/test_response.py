from __future__ import annotations

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.response import ApiResponse


def test_ok_envelope() -> None:
    resp = ApiResponse.ok({"id": 1})
    assert resp.code == 0
    assert resp.message == "ok"
    assert resp.data == {"id": 1}


def test_fail_envelope() -> None:
    resp = ApiResponse.fail(ErrorCode.USER_NOT_FOUND, "用户不存在")
    assert resp.code == 23001
    assert resp.data is None
    assert resp.message == "用户不存在"
