from __future__ import annotations

from enum import IntEnum


class ErrorCode(IntEnum):
    """错误码 5 位 M K NNN。
    M 模块域: 1公用·2identity·3models·4knowledge·5tools·6apps·7runtime·8observability。
    K 类别: 0参数·1鉴权·2权限·3资源·4业务·5限流·9外部/系统。NNN 序号。
    详见 docs/standards.md §6.4。
    """

    SUCCESS = 0

    # 1 公用 / core
    PARAM_INVALID = 10001
    UNAUTHORIZED = 11001
    PERMISSION_DENIED = 12001
    RATE_LIMITED = 15001
    INTERNAL_ERROR = 19001
    EXTERNAL_TIMEOUT = 19002
    CIRCUIT_OPEN = 19003

    # 2 identity
    INVALID_CREDENTIALS = 21001
    USER_NOT_FOUND = 23001
    EMAIL_ALREADY_EXISTS = 23002
