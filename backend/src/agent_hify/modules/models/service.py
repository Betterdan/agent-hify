from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from agent_hify.core.error_codes import ErrorCode
from agent_hify.core.exceptions import NotFoundError
from agent_hify.core.security import decrypt, encrypt
from agent_hify.modules.models import adapter, repository
from agent_hify.modules.models.adapter import ModelRef
from agent_hify.modules.models.models import Model, ModelProvider
from agent_hify.modules.models.schemas import (
    ChatMessage,
    ConnectivityResult,
    InvokeResult,
    ModelIn,
    ModelOut,
    ProviderIn,
    ProviderOut,
)
from agent_hify.modules.observability import service as obs_service
from agent_hify.modules.observability.schemas import TraceIn


def create_provider(session: Session, workspace_id: int, dto: ProviderIn) -> ProviderOut:
    enc = encrypt(json.dumps(dto.credentials)) if dto.credentials else None
    provider = ModelProvider(
        workspace_id=workspace_id,
        type=dto.type,
        name=dto.name,
        base_url=dto.base_url,
        credentials_encrypted=enc,
    )
    repository.insert_provider(session, provider)
    return ProviderOut.model_validate(provider)


def get_decrypted_credentials(session: Session, provider_id: int) -> dict[str, str]:
    provider = repository.get_provider(session, provider_id)
    if provider is None:
        raise NotFoundError(ErrorCode.MODEL_NOT_FOUND, "厂商不存在")
    if not provider.credentials_encrypted:
        return {}
    raw: dict[str, str] = json.loads(decrypt(provider.credentials_encrypted))
    return raw


def create_model(session: Session, workspace_id: int, dto: ModelIn) -> ModelOut:
    model = Model(
        workspace_id=workspace_id,
        provider_id=dto.provider_id,
        model_key=dto.model_key,
        type=dto.type,
        capabilities=dto.capabilities,
        embedding_dim=dto.embedding_dim,
        default_params=dto.default_params,
    )
    repository.insert_model(session, model)
    return ModelOut.model_validate(model)


def list_models(session: Session, workspace_id: int) -> list[ModelOut]:
    return [ModelOut.model_validate(m) for m in repository.list_models(session, workspace_id)]


def resolve_ref(session: Session, model_id: int) -> ModelRef:
    model = repository.get_model(session, model_id)
    if model is None:
        raise NotFoundError(ErrorCode.MODEL_NOT_FOUND, "模型不存在")
    provider = repository.get_provider(session, model.provider_id)
    if provider is None:
        raise NotFoundError(ErrorCode.MODEL_NOT_FOUND, "模型厂商不存在")
    creds = get_decrypted_credentials(session, provider.id)
    return ModelRef(
        provider_id=provider.id,
        provider_type=provider.type,
        model_key=model.model_key,
        api_key=creds.get("api_key"),
        base_url=provider.base_url,
        default_params=model.default_params,
    )


async def invoke(
    session: Session,
    *,
    model_id: int,
    workspace_id: int,
    messages: list[ChatMessage],
    record: bool = True,
) -> InvokeResult:
    """调用模型并记账。

    `record=True`（默认）下成功记 trace(ok)+usage、失败记 trace(error)；成功的 trace/usage
    随请求事务由 router 提交，失败的 error trace 走独立会话提交（请求事务会回滚故须留痕另存）。
    `record=False` 用于连通性探测等不应计入可观测/计费的内部调用。
    """
    ref = resolve_ref(session, model_id)
    payload = [{"role": m.role, "content": m.content} for m in messages]
    started = time.monotonic()
    try:
        result = await adapter.invoke(ref, payload)
    except Exception as exc:
        if record:
            latency_ms = int((time.monotonic() - started) * 1000)
            obs_service.record_trace_committed(
                TraceIn(
                    workspace_id=workspace_id,
                    type="llm_call",
                    status="error",
                    latency_ms=latency_ms,
                    input={"messages": payload},
                    error=str(exc),
                )
            )
        raise
    latency_ms = int((time.monotonic() - started) * 1000)

    if record:
        obs_service.record_trace(
            session,
            TraceIn(
                workspace_id=workspace_id,
                type="llm_call",
                status="ok",
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                cost=Decimal(str(result.cost)),
                latency_ms=latency_ms,
                input={"messages": payload},
                output={"content": result.content},
            ),
        )
        obs_service.record_usage(
            session,
            workspace_id=workspace_id,
            day=datetime.now(UTC).date(),
            model_id=model_id,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost=Decimal(str(result.cost)),
        )
    return result


async def embed(session: Session, *, model_id: int, texts: list[str]) -> list[list[float]]:
    ref = resolve_ref(session, model_id)
    return await adapter.embed(ref, texts)


async def test_connectivity(
    session: Session, *, model_id: int, workspace_id: int
) -> ConnectivityResult:
    try:
        # record=False：连通性探测不计入 trace/usage，避免污染可观测与计费。
        await invoke(
            session,
            model_id=model_id,
            workspace_id=workspace_id,
            messages=[ChatMessage(role="user", content="ping")],
            record=False,
        )
        return ConnectivityResult(ok=True)
    except Exception as exc:  # 归一为连通性失败
        return ConnectivityResult(ok=False, error=str(exc))
