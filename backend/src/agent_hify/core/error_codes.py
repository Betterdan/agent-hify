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
    EXTERNAL_ERROR = 19004

    # 2 identity
    INVALID_CREDENTIALS = 21001
    USER_NOT_FOUND = 23001
    EMAIL_ALREADY_EXISTS = 23002

    # 3 models
    MODEL_NOT_FOUND = 33001
    EMBEDDING_DIM_MISMATCH = 34001
    MODEL_AUTH_FAILED = 39001

    # 4 knowledge
    KB_NOT_FOUND = 43001
    DOC_NOT_FOUND = 43002
    DOC_INGEST_FAILED = 44001

    # 5 tools
    TOOL_NOT_FOUND = 53001
    TOOL_CALL_FAILED = 54001
    TOOL_DISABLED = 54002

    # 6 apps
    APP_NOT_FOUND = 60003

    # 7 runtime
    CONVERSATION_NOT_FOUND = 70001
    AGENT_INTERNAL_ERROR = 79001
