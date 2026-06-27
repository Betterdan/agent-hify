# agent-hify 工程规范（数据 / 索引 / 分页 / 接口 / 外部调用）

> 版本：v1（2026-06-27）｜ 仅适用于本项目
> 定位：**细则的权威事实来源**。DESIGN.md 管架构与决策，本文件管"每张表/每个接口/每次外部调用"落地时必须遵守的具体规矩。
> 配套：[DESIGN.md](../DESIGN.md) · [CLAUDE.md](../CLAUDE.md)
> 新增表 / 接口 / 外部调用时按本文件逐条核查（可用 `schema-review` skill）。

---

## 1. 数据表通用字段规范

所有顶层业务表必须包含以下通用字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `bigint` PK，`generated always as identity` | 自增主键；对外暴露的资源（如发布分享）另用随机 `share_token`，不直接暴露自增 id |
| `workspace_id` | `bigint` FK→workspaces | 多工作区预埋，默认 `default`，始终携带 |
| `created_at` | `timestamptz` | UTC；插入时写入 |
| `updated_at` | `timestamptz` | UTC；每次更新刷新 |
| `deleted_at` | `timestamptz` NULL | **仅软删除表**（见 §2）；NULL=未删除 |

**命名**：表名/字段名一律 **`snake_case` 小写下划线**，表名用复数（`models`、`knowledge_bases`）。
**枚举**：字符串 + `CHECK` 约束（迁移友好，胜过 PG enum）。
**JSON**：用 `JSONB`。
**布尔**：`enabled bool default true` 之类，不用 0/1 整型。

---

## 2. 软删除规范（D1=A 选择性软删除）

| 类别 | 表 | 删除方式 |
|---|---|---|
| **配置 / 用户可见** | `apps`、`knowledge_bases`、`models`、`model_providers`、`tools`、`users` | **软删除**：置 `deleted_at`，可恢复+留痕 |
| **追加型日志 / 派生数据** | `traces`、`messages`、`conversations`、`usage_daily`、`chunks`、`documents`、`annotations` | **物理删除 / 归档**（见 §4），不背 `deleted_at` |

规则：
1. 软删除表的所有查询**默认追加 `WHERE deleted_at IS NULL`**（在 repository 层统一封装，避免漏写）。
2. `deleted_at` **必须进相关查询索引**（通常作为复合索引/部分索引的过滤条件）。
3. **唯一约束需与软删共存**：原 `UNIQUE(workspace_id, name)` 改为**部分唯一索引** `... WHERE deleted_at IS NULL`，否则删除后无法复用同名。
4. 级联：软删除父表时，子数据如何处理须在 service 层显式决定（不依赖 DB 级联，DB 级联只用于物理删除表）。

---

## 3. 索引设计规范

1. **所有外键建 btree 索引**（`workspace_id`、各 `*_id`、`created_by`）。
2. **逻辑删除字段必须进索引**：软删除表的高频查询索引把 `deleted_at` 纳入（复合索引列之一，或用 `WHERE deleted_at IS NULL` 部分索引）。
3. **组合索引：等值列在前，范围/排序列在后**。例：`messages(conversation_id, created_at)`、`conversations(app_id, created_at DESC)`。
4. **唯一约束用 UNIQUE INDEX，不只在代码层校验**；与软删共存时用部分唯一索引（§2.3）。
5. **禁止在大文本字段建索引**（`chunks.content`、各 `error`/`note` 等）；需要全文检索另上 GIN/`tsvector`，v1 不做。
6. **多对多双向索引**：若用关联表，两个方向的外键都建索引。
   - 本项目 `apps.config` 用 `kb_ids[]`/`tool_ids[]`（JSONB 数组）持有引用，**不是关联表**——故无需双向索引；反向"哪些 app 用了某 kb"为低频运维查询，需要时对该 JSONB 键加 GIN，不预建。
7. **JSONB 按键查询**才加 GIN（如 `models.capabilities` 含 vision）；v1 数据量小，按需再加。
8. **向量索引**：`chunks.embedding` 用 **HNSW + `vector_cosine_ops`**（见 DESIGN.md §11.2）。

---

## 4. 大表预判与归档

| 表 | 增长来源 | 量级预判 | 策略 |
|---|---|---|---|
| `traces` | 每次 LLM/工具/检索调用 1+ 行 | **最快**，可月百万级 | 按 `created_at` 月分区或定期归档；保留期可配（如 90 天），过期转冷存/删除 |
| `messages` | 每轮对话 | 较快 | 游标分页（§5）；长期可按 `conversation_id` 归档 |
| `chunks` | 文档摄取 | 取决于语料 | <10 万 chunk HNSW 无感；超量再分区/独立向量库（DESIGN.md §17） |
| `usage_daily` | 每天聚合 | 慢 | 无需特殊处理 |

原则：**大表查询必须走索引 + 限定范围（时间/外键）+ 强制 LIMIT**，禁止全表扫描与无界排序。

---

## 5. 分页规范（D2=A 混合）

| 场景 | 表 | 方式 |
|---|---|---|
| 大 / 追加型 | `messages`、`conversations`、`traces` | **游标分页** |
| 小配置列表（需跳页） | `models`、`apps`、`knowledge_bases`、`tools`、`users` | offset 分页 |

**游标分页**：
- 游标 = `(created_at, id)` 复合，编码成不透明 `cursor` 串（base64）。
- 查询：`WHERE (created_at, id) < (:c_ts, :c_id) ORDER BY created_at DESC, id DESC LIMIT :n`。
- 响应：`{ items, next_cursor, has_more }`；`next_cursor=null` 表示到底。
- **优点**：数据量上来不改代码、不漏不重。

**offset 分页**：
- 入参 `?page=&page_size=`（默认 20）；响应 `{ items, total, page, page_size }`。
- **`count` 单独查询，且仅第一页（`page==1`）返回 `total`**；后续翻页 `total` 返回 `null`，不复查，避免大表重复 count。

---

## 6. 接口契约规范

### 6.1 路径与方法
- RESTful：`/api/v1/<模块复数资源>`，如 `/api/v1/models`、`/api/v1/apps/{id}/chat`。
- 资源化复数 URL；字段 `snake_case`；时间 ISO-8601 UTC。

### 6.2 统一响应（D3=B 全包装，始终 HTTP 200）
所有业务接口（非健康探针/非 SSE 流体）统一返回 **`ApiResponse[T]`**，**HTTP 状态始终 200**，成败由 `code` 区分：

```jsonc
// 成功
{ "code": 0, "message": "ok", "data": { /* T，资源或 Page[T] */ } }
// 失败
{ "code": 40401, "message": "模型不存在", "data": null, "details": {} }
```

- 用 Pydantic 泛型 `ApiResponse[T]` 定义，使 OpenAPI 仍能描述、orval 仍能生成前端类型；前端统一取 `resp.data`、按 `resp.code` 判错。
- **例外**：`/health` 等基础设施探针按真实 HTTP 状态（供 Docker/LB 判活）；SSE 流式接口走事件协议（DESIGN.md §9），错误走 `error` 事件。

### 6.3 空值处理
- 列表字段为空 → 返回 `[]`，**不返回 `null`**。
- 字符串字段为空 → 返回 `""`，**不返回 `null`**（语义上"未知/不适用"才用 `null`，并在 schema 标注）。
- 对象不存在 → 返回 `null`。
- `data` 在失败时为 `null`。

### 6.4 错误码体系（按模块分段）

`code` 为整数：`0` = 成功；错误码为 **5 位 `M K NNN`**，**靠首位即可定位出错模块**。集中登记，新增必须进注册表并对应一个常量名。

- **`M`（1 位）= 模块域**：`1` 公用(core) · `2` identity · `3` models · `4` knowledge · `5` tools · `6` apps · `7` runtime · `8` observability
- **`K`（1 位）= 类别**：`0` 参数/校验 · `1` 鉴权(未登录) · `2` 权限不足 · `3` 资源不存在/冲突 · `4` 业务规则/状态非法 · `5` 限流 · `9` 外部依赖/系统(超时/熔断/内部错误)
- **`NNN`（3 位）= 模块内序号** `001`–`999`

| 模块域 `M` | 模块 | 示例 code / 常量 |
|---|---|---|
| 1 | 公用 core | `10001 PARAM_INVALID`、`11001 UNAUTHORIZED`、`12001 PERMISSION_DENIED`、`15001 RATE_LIMITED`、`19001 INTERNAL_ERROR`、`19002 EXTERNAL_TIMEOUT`、`19003 CIRCUIT_OPEN` |
| 2 | identity | `21001 INVALID_CREDENTIALS`、`23001 USER_NOT_FOUND` |
| 3 | models | `33001 MODEL_NOT_FOUND`、`34001 EMBEDDING_DIM_MISMATCH`、`39001 MODEL_AUTH_FAILED`、`39002 MODEL_TIMEOUT` |
| 4 | knowledge | `43001 KB_NOT_FOUND`、`44001 DOC_INGEST_FAILED` |
| 5 | tools | `53001 TOOL_NOT_FOUND`、`59001 TOOL_TIMEOUT` |
| 6 | apps | `63001 APP_NOT_FOUND`、`64001 APP_NOT_PUBLISHED` |
| 7 | runtime | `74001 MAX_ITERATIONS_EXCEEDED` |
| 8 | observability | （多为内部，少对外）|

- **通用 vs 模块专属**：跨模块通用的错（参数、鉴权、限流、内部错、通用外部超时/熔断）归 **公用域 1xxxx**；模块特有的错（如 `MODEL_AUTH_FAILED`、`TOOL_TIMEOUT`）归各模块的 `9` 类别。
- 与 `AppError` 体系对应：`AppError(code:int, reason:str 常量, message, http_status=200, details)`，core 中央处理器统一转 §6.2 信封。
- 注册表维护在 `core`（`core/error_codes.py` 的枚举），`schema-review` 校验新码已登记、首位模块域正确、无重号。

---

## 7. 外部调用规范（所有出网调用必须遵守）

适用：`models.invoke/embed`（LLM/embedding API）、`tools.call_tool`（api/mcp 类工具）、文档摄取中的 embedding 批量调用。统一封装在 `core` 的外部调用包装中复用（架构见 DESIGN.md §16）。

| 维度 | 规则（默认值，可按 provider 配置覆盖） |
|---|---|
| **超时** | 连接超时 5s；读超时：非流式 30s、流式 60s（首 token 等待）、embedding 批 30s。**禁止无超时调用**。 |
| **重试** | 仅对**可重试错误**（连接错误、5xx、429、超时）重试；指数退避 + 抖动；最多 2 次（共 3 次）；**非幂等/4xx 鉴权/参数错误不重试**。 |
| **熔断** | 按 **provider 维度** 熔断：滑动窗口失败率超阈值→打开（快速失败返回 `CIRCUIT_OPEN`），半开探测恢复。 |
| **隔离（bulkhead）** | 每 provider 独立 httpx 连接池 + 信号量限并发；异步重活走 Celery 独立队列，避免一个慢厂商拖垮全局。 |
| **可观测** | 每次外部调用经 `observability.trace` 记录 input/output/latency/tokens/status；失败记 error。 |

---

## 8. 核查清单（schema-review 用）

新增/变更**表**时：
- [ ] 含 `id`/`workspace_id`/`created_at`/`updated_at`；软删表含 `deleted_at`
- [ ] 字段 `snake_case`；枚举用 CHECK；JSON 用 JSONB
- [ ] 外键都建索引；高频查询有复合索引（等值在前、范围在后）
- [ ] 软删表：查询默认过滤 `deleted_at IS NULL`；唯一约束改部分唯一索引
- [ ] 唯一性用 UNIQUE INDEX；未在大文本字段建索引
- [ ] 判断是否大表 → 是则有范围限定 + LIMIT + 归档/分区考虑

新增/变更**接口**时：
- [ ] 路径 `/api/v1/...` RESTful；响应 `ApiResponse[T]`、HTTP 200
- [ ] 列表→`[]`、字符串→`""`、不存在→`null` 的空值规则
- [ ] 错误码已在注册表登记、无重号、有常量名
- [ ] 列表接口选对分页方式（大表游标 / 小列表 offset，count 仅首页）

新增**外部调用**时：
- [ ] 有超时；可重试错误才重试；纳入 provider 熔断与隔离；经 observability 记录
```
