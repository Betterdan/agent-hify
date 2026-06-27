from __future__ import annotations

from agent_hify.core.error_codes import ErrorCode


def test_success_is_zero() -> None:
    assert ErrorCode.SUCCESS.value == 0


def test_codes_unique_and_five_digit() -> None:
    values = [c.value for c in ErrorCode if c is not ErrorCode.SUCCESS]
    assert len(values) == len(set(values)), "错误码不得重号"
    assert all(10000 <= v <= 89999 for v in values), "错误码须为 5 位 M K NNN"


def test_first_digit_is_known_module_domain() -> None:
    for c in ErrorCode:
        if c is ErrorCode.SUCCESS:
            continue
        assert int(str(c.value)[0]) in range(1, 9), f"{c.name} 首位模块域非法"
