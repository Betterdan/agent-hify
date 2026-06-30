# Skill: 架构纪律

> 本文件描述 agent-hify 的架构强约束。实现任何功能前先核对，评审时作为检查清单。

---

## 模块依赖层级（单向，从高到低）

```
L4: runtime（跨模块编排）
L3: apps, knowledge, tools
L2: models（模型网关）
L1: observability
L0: core（配置/DB/安全/异常/日志）
```

规则：
- 只能依赖**更低层**模块
- 唯一例外：任何层都可以向下调用 `observability`（L1）
- `import-linter` 在 CI 强制执行，变更依赖关系必须同步更新 `pyproject.toml` 合约

---

## 跨模块边界规则

**禁止**：
- 跨模块直接 import `repository.py`、`models.py`（ORM 类）
- 在 router 里写业务逻辑或跨模块编排
- 直接访问其他模块的数据库表

**允许**：
- 调用其他模块的 `service.py` 公共函数
- 传递 Pydantic Schema（DTO）或基本类型

---

## 模块内分层

```
router → service → repository
schemas（DTO）/ models（ORM）分离
```

- `router`：只做鉴权 + 参数校验 + 调本模块 service，不写业务逻辑
- `service`：业务逻辑，可调 repository 和其他模块 service
- `repository`：只做 DB 操作，不写业务逻辑
- `schemas`：Pydantic DTO，用于 API 输入输出
- `models`：SQLAlchemy ORM，只在 repository 层使用

---

## 接口规范

**统一响应信封**：
```json
{ "code": 0, "message": "ok", "data": <payload>, "details": null }
```

**错误码**：
- 范围：10000–89999，首位 1–8
- 0 = 成功

**分页**：
```json
{ "items": [...], "total": N, "page": P, "page_size": S }
```

**SSE 事件格式**：
```
event: <type>
data: <json>

```
- 事件类型：`message`（delta）/ `usage` / `done` / `error` / `step`（Agent）

---

## 数据库规范（来自 docs/standards.md）

- 所有表必须有 `id`（serial primary key）、`created_at`、`updated_at`
- 软删除用 `deleted_at`，不物理删除用户数据
- 迁移文件不可修改已有迁移，只能新增
- `workspace_id` 必须出现在所有业务表（预埋多工作区）

---

## 安全规范

- API Key 用 `core.security.encrypt()` 加密存储，不明文
- 所有外部调用必须有超时（LiteLLM、HTTP 工具、MCP）
- SSE 异常：固定字符串 + `logger.error`，不暴露 `str(exc)`
- DB 并发 upsert：用 `pg_insert ON CONFLICT`，不用 read-then-write

---

## 检查清单（实现完成后自查）

- [ ] 新模块/函数没有跨层 import
- [ ] router 没有业务逻辑
- [ ] 跨模块调用只用 service 接口
- [ ] 所有外部调用有 timeout
- [ ] 新表有 workspace_id、created_at、updated_at
- [ ] 错误码在 10000–89999 范围
- [ ] SSE 错误分支不暴露内部信息
- [ ] import-linter 合约若有变更已同步更新
