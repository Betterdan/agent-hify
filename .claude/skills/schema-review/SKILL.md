---
name: schema-review
description: Use when adding or changing a database table/migration, an API endpoint, an error code, or an external (LLM/tool/embedding) call in the agent-hify project — before writing the migration/route/client. Reviews the change against docs/standards.md (通用字段·软删·索引·分页·统一响应·空值·错误码·外部调用韧性). Symptoms it catches: missing deleted_at, no partial unique index, missing FK/composite index, wrong pagination, unregistered or wrong-prefix error code, no timeout on外部调用.
---

# schema-review（agent-hify 项目）

按项目工程规范核查一处"新增/变更的表 / 接口 / 错误码 / 外部调用"。**唯一事实来源是仓库根的 [`docs/standards.md`](../../../docs/standards.md)**；本 skill 是核查驱动器，规则细节/取舍以 standards.md 为准，冲突时以 standards.md 为准。

## 何时用
- 新增或改 数据表 / Alembic 迁移
- 新增或改 HTTP 接口
- 新增 错误码
- 新增 外部调用（`models.invoke/embed`、`tools.call_tool`、摄取 embedding）

## 怎么评审
1. **先读** `docs/standards.md`（不要凭记忆）。
2. 按下面**对应维度**的清单逐条核；每条给结论：✅通过 ／ ❌违反（必附**具体修法**）／ ➖不适用（必附原因）。
3. 末尾给**总结论**：`通过` 或 `需改` + 必改项编号列表。
4. 只评审、列修法；不擅自改代码（除非调用者要求）。

### 维度 A · 数据表（standards §1–4）
- [ ] 含 `id`/`workspace_id`/`created_at`/`updated_at`
- [ ] **配置/用户可见表**含 `deleted_at`；查询默认 `WHERE deleted_at IS NULL`
- [ ] 软删表的唯一约束 = **部分唯一索引**（`WHERE deleted_at IS NULL`），不是普通 UNIQUE
- [ ] 字段 `snake_case`；枚举用 CHECK；JSON 用 JSONB；布尔用 bool
- [ ] 所有外键建索引；高频查询有复合索引（**等值列在前、范围/排序列在后**）
- [ ] `deleted_at` 进相关查询索引（或部分索引）
- [ ] 唯一性用 UNIQUE INDEX，不只在代码层校验
- [ ] 未在大文本字段（content/error/note）建索引
- [ ] 判断是否大表（traces/messages/chunks 类）→ 是则有范围限定 + LIMIT + 归档/分区考虑
- [ ] 向量列用 HNSW + `vector_cosine_ops`，检索带 `WHERE kb_id` + `LIMIT`

### 维度 B · 接口（standards §5–6）
- [ ] 路径 `/api/v1/<复数资源>` RESTful；字段 snake_case；时间 ISO-8601 UTC
- [ ] 响应包成 `ApiResponse[T]`、**始终 HTTP 200**（探针/SSE 例外）
- [ ] 空值：列表→`[]`、字符串→`""`、对象不存在→`null`
- [ ] 列表接口选对分页：**大/追加型用游标，小配置列表用 offset**；`total` 仅第一页查询返回

### 维度 C · 错误码（standards §6.4）
- [ ] 形如 5 位 `M K NNN`；**首位模块域正确**（1公用·2identity·3models·4knowledge·5tools·6apps·7runtime·8observability）
- [ ] 第二位类别合理（0参数·1鉴权·2权限·3资源·4业务·5限流·9外部/系统）
- [ ] 通用错归 1xxxx；模块特有外部错归该模块 9 类别
- [ ] 已在 `core/error_codes.py` 登记、有常量名、无重号

### 维度 D · 外部调用（standards §7）
- [ ] 经 core 统一外部调用包装，不裸调 httpx
- [ ] **有超时**（连接 5s / 非流式读 30s / 流式 60s / embedding 30s）
- [ ] 仅可重试错误（连接/5xx/429/超时）重试；4xx 鉴权/参数不重试
- [ ] 纳入 provider 维度熔断 + 连接池/信号量隔离
- [ ] 经 `observability.trace` 记录 latency/tokens/status/error

## 输出格式（契约）
对每个涉及的维度输出一张表 `| 检查项 | 结论 | 说明/修法 |`，最后一行：
`总结论：通过` 或 `总结论：需改 —— [必改项编号]`。

## 常见漏检（无此 skill 时的典型失误）
- 配置表漏 `deleted_at`，或软删后用普通 UNIQUE 导致同名无法复用 → 用部分唯一索引
- 外键/复合索引漏建，或复合索引把范围列放等值列前面
- 大表（traces/messages）用了 offset 分页 → 应游标
- 错误码首位模块域用错、未登记、或与 HTTP 语义混编（本项目按**模块**分段，非 HTTP 语义）
- 外部调用无超时（违反 CLAUDE.md 编码准则）
