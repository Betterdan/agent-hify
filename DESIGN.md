# agent-hify 总体设计文档

> 版本：v0.5（架构设计定稿）｜ 日期：2026-06-27
> 状态：架构设计已定稿，进入工程搭建
> 配套：[METHODOLOGY.md](./METHODOLOGY.md) · [CLAUDE.md](./CLAUDE.md) · [docs/standards.md](./docs/standards.md)（工程细则权威） · [docs/competitive-brief-agent-platforms.md](./docs/competitive-brief-agent-platforms.md)

> **v0.5 变更摘要**（2026-06-27 设计评审）：补足外部调用韧性（§16）、每层职责（§6.4）、大表预判（§12.2）、可扩展性演进（§17）；统一响应改企业式 `ApiResponse[T]`+错误码体系+空值规范（§9）；引入选择性软删除（§10）；分页改混合（游标/offset，§9.4）。数据表/索引/分页/接口/外部调用的**逐条细则统一落在 [docs/standards.md](./docs/standards.md)**，本文件只留架构与决策。

## 目录
1. 背景与目标
2. 竞品调研结论
3. 功能范围
4. 技术选型与编码规范
5. 总体架构（模块化单体 + core 基础层）
6. 模块职责边界、依赖分层与跨模块调用规范（含 §6.4 每层职责）
7. 数据流向
8. 代码组织
9. 接口契约（统一响应 / 错误码 / 空值 / 分页）
10. 数据模型（定稿）
11. 索引策略（定稿）
12. 性能预判与大表预判
13. 运维预期
14. 第一阶段 P0 范围
15. 错误处理与测试策略
16. 外部调用韧性（超时 / 重试 / 熔断 / 隔离）
17. 可扩展性与演进路径

> **方法论阶段映射**：§1–4、13=文字归档；§5–12、16–17=架构设计；行为指令见 CLAUDE.md；§14 起进入工程搭建/功能实现。

---

## 1. 背景与目标

用方法论驱动，落地一个**类 Dify、面向 50 人内规模**的 LLM 应用 / Agent 平台。**首要目标：方法论优先**——走通"问题界定→设计→实现→评估→迭代"闭环并沉淀。

## 2. 竞品调研结论（摘要）

详见 [competitive-brief](./docs/competitive-brief-agent-platforms.md)。编排/RAG/Agent/模型接入已饱和（正面重做必败）；**空白在"评估—可观测—迭代方法论闭环"**，作为差异化主张。不做通用自动化、不拼集成数量、不拼分发生态。

## 3. 功能范围

**第一版硬核**：模型管理（含视觉输入）→ 聊天助手 → RAG → 工具集成（MCP + 外部 API）→ Agent → 可观测基线 + 评估钩子。多模态限定为**视觉输入**。

**迭代版图（后续）**：Rerank · Prometheus · 多工作区(已预埋) · 细粒度 RBAC · 文档增量更新 · 文生图/音频 · embed iframe · 负载均衡/配额 · **工作流编排**。

---

## 4. 技术选型与编码规范

### 后端（Python）
| 项 | 选型 |
|---|---|
| 语言/运行时 | Python 3.12+，全量类型注解，`from __future__ import annotations` |
| Web 框架 | FastAPI（异步） |
| 模型网关 | LiteLLM |
| ORM/迁移 | SQLAlchemy 2.0（`Mapped[]` 类型化）+ Alembic |
| DTO/配置 | Pydantic v2 / pydantic-settings |
| DB | PostgreSQL 16 + pgvector |
| 异步 | Celery + Redis |
| RAG | LlamaIndex(仅解析/分块) + pgvector + 手写检索 |
| Agent | 手写 ReAct / function-calling 循环 |
| MCP | 官方 MCP Python SDK |

**编码规范（业界主流）**：
- **依赖管理**：`uv`（现代、快）+ `pyproject.toml`。
- **Lint+格式化**：`Ruff`（取代 black/isort/flake8，统一格式化与 lint）。
- **类型检查**：`mypy`（strict 倾向）。
- **测试**：`pytest` + `pytest-asyncio` + `httpx.AsyncClient`。
- **架构约束**：`import-linter`（CI 强制模块依赖分层，见 §6）。
- 命名：模块/函数 `snake_case`，类 `PascalCase`，常量 `UPPER_SNAKE`；Google 风格 docstring；12-factor 配置（全部走环境变量 → pydantic-settings）。

### 前端（React）
| 项 | 选型 |
|---|---|
| 构建 | Vite |
| 语言 | TypeScript（`strict: true`） |
| UI | Ant Design |
| 服务端状态 | TanStack Query |
| 路由 | React Router |
| 客户端状态 | 必要时 Zustand（v1 尽量不引入） |
| 流式 | SSE |

**编码规范（业界主流）**：
- **Lint/格式化**：ESLint（`typescript-eslint`）+ Prettier。
- **目录结构**：**feature-based（特性切片）**，而非按文件类型堆（见 §8）。
- **API 客户端**：**由后端 OpenAPI 自动生成 TS 类型与请求**（`orval` 或 `openapi-typescript`）——接口契约单一事实来源，杜绝前后端类型漂移（见 §9）。
- **测试**：Vitest + React Testing Library（组件冒烟为主）。
- 命名：组件 `PascalCase`、hook `useXxx`、路径别名 `@/`。

---

## 5. 总体架构（模块化单体 + core 基础层）

模块化单体：一个 FastAPI 应用，内部分**基础层 core** 与**有界业务模块**。core 提供横切基础设施（配置、异常、DB、安全、日志、公共类型），所有模块构建其上。业务模块只通过彼此的 `service` 接口通信。

```mermaid
flowchart TD
    subgraph API[API 层 / FastAPI app 装配]
      MAIN[main.py: 挂载各模块 router + 中间件 + 异常处理器]
    end
    subgraph L_App[应用/编排层]
      RT[runtime 执行引擎]
      APP[apps 应用定义]
    end
    subgraph L_Cap[能力层]
      MOD[models 模型网关]
      KB[knowledge RAG]
      TOOL[tools 工具]
    end
    subgraph L_Base[基础业务层]
      ID[identity 身份/工作区]
      OBS[observability 可观测/评估]
    end
    subgraph L0[core 基础层]
      CFG[config]:::c
      EXC[exceptions+handlers]:::c
      DB[db/session/Base]:::c
      SEC[security 加密/哈希/token]:::c
      LOG[logging]:::c
      TYP[types: ContentBlock 等]:::c
    end
    MAIN --> RT & APP & MOD & KB & TOOL & ID & OBS
    RT --> APP & MOD & KB & TOOL & OBS
    KB --> MOD
    MOD & KB & TOOL & APP & ID & OBS --> L0
    classDef c fill:#eef,stroke:#88a;
```

> 取消了原 `console` 伪模块：**路由按模块就近放**（每模块 `router.py`），`app/main.py` 负责装配（挂载路由、中间件、异常处理器、OpenAPI）。"管理控制台"是前端概念，后端只暴露各模块 API。

---

## 6. 模块职责边界、依赖分层与跨模块调用规范

### 6.1 依赖分层（单向、无环）
层级越低越基础；**只能依赖更低层**。`observability` 是 L1 横切，允许被任意上层"向下"调用记录。

| 层 | 模块 | 依赖 |
|---|---|---|
| **L0 core** | config / exceptions / db / security / logging / types | 无（仅标准库与第三方） |
| **L1** | `identity`、`observability` | core |
| **L2** | `models`、`tools` | core, identity, observability |
| **L2'** | `knowledge` | core, identity, observability, **models** |
| **L3** | `apps` | core, identity（仅存配置，按 id 引用 models/kb/tools，不调用它们） |
| **L4** | `runtime` | core, apps, models, knowledge, tools, observability |
| **L5** | API 装配（main + 各模块 router） | 各自模块 service + core |

**关键无环设计**：`apps` 不依赖 `runtime`/`models`/`knowledge`/`tools`——它只持久化"配置"（`model_id`、`kb_ids`、`tool_ids` 等都是 id）。运行时由 `runtime` 读取配置并解析、调用各能力模块。

### 6.2 模块职责边界（拥有 / 不拥有）

| 模块 | 拥有（owns） | **不**拥有 | 对外接口（service）举例 |
|---|---|---|---|
| **core** | 配置、DB session、Base ORM、异常体系+处理器、加密/哈希/token、结构化日志、公共类型(ContentBlock/Page) | 任何业务数据 | `get_settings()`, `get_session()`, `encrypt()/decrypt()`, `AppError` 家族 |
| **identity** | users、workspaces、roles、登录会话 | 资源级归属（只盖 `created_by`） | `get_current_user()`, `require_role()`, `current_workspace()` |
| **models** | model_providers、models 注册表、加密凭证 | 会话/消息；模型"如何被用" | `invoke(ref, messages, stream)`, `embed(ref, texts)`, `test_connectivity(provider)` |
| **knowledge** | knowledge_bases、documents、chunks、摄取管线、检索 | 谁用哪个 KB（apps 配置）；生成式调用 | `retrieve(kb_id, query, top_k, threshold)`, `ingest(doc)`（异步） |
| **tools** | tools 注册表(builtin/api/mcp)、工具凭证、Tool 协议与调用 | 何时调用工具（runtime 决定） | `list_tools(ids)`, `call_tool(id, args)`, `get_specs(ids)` |
| **apps** | 应用定义+配置(chat/agent)、发布状态 | 执行；会话 | `get_config(app_id)`, CRUD |
| **runtime** | 执行引擎、ReAct 循环、content-block 组装、流式；**conversations、messages** | 各能力的配置（读自 apps/models 等） | `run_conversation(app_id, input, stream)`, `list_conversations(app_id)` |
| **observability** | traces、usage、annotations、评估钩子 | 业务数据 | `trace(...)`, `record_usage(...)`, `annotate(...)`, `run_eval_hook(...)` |

### 6.3 跨模块调用规范（强约束）
1. **只走 service 接口**：模块对外能力仅通过自身 `service.py` 的公开函数暴露；禁止 import 其他模块的 `repository.py` / `models.py`（ORM）/ 直接访问其表。
2. **跨边界只传 DTO**：参数与返回值只用 Pydantic schema 或基本类型，**不得跨模块传 SQLAlchemy ORM 实例**。
3. **持久化隔离**：每模块 repository 只碰自己的表；需要别家数据 → 调对方 service。
4. **单向无环**：依赖只能向下（见 §6.1），`import-linter` 在 CI 强制；唯一例外是任何模块可"向下"调用 `observability`（横切）。
5. **横切归 core**：配置/异常/DB/安全/日志/公共类型统一在 `core`，禁止各模块各造一套。
6. **路由薄**：`router.py` 只做鉴权+参数校验+调用本模块 service，不写业务、不跨模块编排；跨模块编排只发生在 `runtime`。
7. **异步任务**：模块通过 `worker` 中定义的 Celery 任务入队；任务体内调用模块 service（不跨边界直连 repository）。

### 6.4 每层职责边界（按层而非按模块）

§6.2 是按模块的 owns/not-owns；这里是按**层**的职责与可依赖范围，明确"谁能调谁、谁不写什么"。

| 层 | 核心职责 | 可依赖 | 禁止 |
|---|---|---|---|
| **L0 core** | 横切基础设施：配置、DB session/Base、异常体系+处理器、安全(加密/哈希/token)、日志、公共类型、外部调用韧性包装(§16) | 仅标准库/第三方 | 任何业务逻辑、任何业务表 |
| **L1 identity / observability** | identity：认证/工作区/角色；observability：trace/usage/评估钩子（横切，可被任意上层向下调用） | core | 互相依赖业务；observability 不反向驱动业务 |
| **L2 models / tools** | 能力提供：模型网关调用、工具注册与调用 | core, identity, observability | 持有会话/消息；决定"何时被用" |
| **L2' knowledge** | RAG：摄取/分块/检索 | + models（embed） | 生成式编排；决定"谁用哪个 KB" |
| **L3 apps** | 仅持久化应用**配置**（以 id 引用 model/kb/tool） | core, identity | 依赖/调用 runtime/models/knowledge/tools；执行 |
| **L4 runtime** | **唯一跨模块编排者**：读 apps 配置→调 models/knowledge/tools→组装 content-block→流式；持有 conversations/messages | core, apps, models, knowledge, tools, observability | 被下层依赖（无人依赖 runtime） |
| **L5 API 装配** | main 挂载 router/中间件/异常处理器/OpenAPI；各模块 `router` 鉴权+校验+调本模块 service | 各自模块 service + core | 在 router 写业务或跨模块编排（编排只在 runtime） |

**一句话规则**：能力模块（L2/L2'）互不感知，只被 runtime 编排；`apps` 只存配置不执行；跨模块组合**只在 runtime**；横切只在 core 与 observability。

---

## 7. 数据流向

### 7.1 聊天 + RAG（流式）
```mermaid
sequenceDiagram
    participant FE as 前端
    participant R as router(apps/chat)
    participant RT as runtime
    participant AP as apps
    participant KB as knowledge
    participant MD as models
    participant OB as observability
    FE->>R: POST /api/v1/apps/{id}/chat (SSE)
    R->>RT: run_conversation(app_id, input, stream)
    RT->>AP: get_config(app_id)
    AP-->>RT: AppConfig(model_id, prompt, kb_ids…)
    opt 挂了知识库
      RT->>KB: retrieve(kb_id, query, top_k, threshold)
      KB->>MD: embed(query)
      MD-->>KB: vector
      KB-->>RT: chunks
      RT->>OB: trace(retrieval)
    end
    RT->>MD: invoke(model, messages+context, stream=true)
    MD-->>RT: token 流
    RT-->>FE: SSE message 事件（逐 token）
    RT->>OB: trace(llm_call) + record_usage()
    RT->>RT: 持久化 conversation/messages(content-blocks)
```

### 7.2 Agent（ReAct 循环）
```mermaid
sequenceDiagram
    participant RT as runtime
    participant MD as models
    participant TL as tools
    participant KB as knowledge
    participant OB as observability
    loop 直到完成 / 达 max_iterations
      RT->>MD: invoke(messages + tool_specs)
      alt 模型要求调用工具
        MD-->>RT: tool_use(name,args)
        RT->>TL: call_tool(id,args)  %% 或 KB.retrieve
        TL-->>RT: tool_result
        RT->>OB: trace(agent_step/tool_call)
        RT-->>RT: 追加 tool_result 到 messages
      else 产出最终答复
        MD-->>RT: final text
        RT->>OB: trace(llm_call)+record_usage()
      end
    end
```

### 7.3 文档摄取（异步）
```mermaid
sequenceDiagram
    participant FE as 前端
    participant R as router(knowledge)
    participant KB as knowledge.service
    participant Q as Celery/Redis
    participant W as worker
    participant MD as models
    FE->>R: 上传文档
    R->>KB: create document(status=pending) + 落文件卷
    KB->>Q: enqueue ingest(document_id)
    R-->>FE: 202 + document_id（前端轮询/SSE 进度）
    W->>KB: 取 document
    W->>W: 解析(LlamaIndex) → 分块
    W->>MD: embed(chunks)
    MD-->>W: vectors
    W->>KB: 存 chunks(pgvector) + status=done/failed
```

---

## 8. 代码组织

### 后端（src 布局 + 模块内统一分层）
```
backend/
├─ pyproject.toml            # uv + ruff + mypy + pytest 配置
├─ alembic/                  # 迁移
├─ src/agent_hify/
│  ├─ main.py                # FastAPI 装配：挂载各模块 router、中间件、异常处理器
│  ├─ core/                  # L0 基础层
│  │  ├─ config.py           #   pydantic-settings
│  │  ├─ db.py               #   engine/session/Base
│  │  ├─ exceptions.py       #   异常体系 + FastAPI 处理器
│  │  ├─ security.py         #   哈希/加密/token
│  │  ├─ logging.py
│  │  ├─ pagination.py       #   Page[T]
│  │  └─ types.py            #   ContentBlock 等公共类型
│  ├─ modules/               # 业务模块（每个内部分层一致）
│  │  ├─ identity/  models/  knowledge/  tools/  apps/  runtime/  observability/
│  │  │   每个含: router.py  service.py  repository.py  schemas.py  models.py
│  └─ worker/                # Celery app + tasks
└─ tests/                    # 单元 + 集成
```
**模块内分层约定**：`router`(HTTP，薄) → `service`(业务，唯一对外入口) → `repository`(本模块表 ORM 操作)；`schemas`(Pydantic DTO，跨边界只传它) / `models`(SQLAlchemy ORM，模块私有)。

### 前端（feature-based）
```
frontend/
├─ src/
│  ├─ app/                   # 应用装配：router、Query Client、antd 主题、布局
│  ├─ features/              # 按特性切片
│  │  ├─ auth/  models/  knowledge/  apps/  chat/  observability/
│  │  │   每个含: api/(生成的 hooks 之上的封装)  components/  hooks/  types.ts  routes.tsx
│  ├─ shared/               # 跨特性复用：components(ui)、hooks、utils
│  ├─ lib/
│  │  └─ api/               # 由 OpenAPI 生成的 TS 客户端(orval 输出，勿手改)
│  └─ main.tsx
├─ orval.config.ts          # 指向后端 /openapi.json
└─ package.json
```

---

## 9. 接口契约

> 接口/数据/分页/错误码/空值的**逐条细则与核查清单见 [docs/standards.md](./docs/standards.md)**；本节只给架构级约定。

### 9.1 对外 HTTP API（OpenAPI 为单一事实来源）
- 后端用 FastAPI + Pydantic 定义 → 暴露 `/openapi.json` → 前端用 **orval** 生成 TS 类型与 TanStack Query hooks。**前端不手写接口类型**，从根上消除漂移。
- 风格：REST，资源化复数 URL，前缀 `/api/v1`；字段 `snake_case`；时间 ISO-8601 UTC。
- 鉴权：登录后 Bearer Token；除登录/health 外均需鉴权。
- 版本：路径 `/api/v1`，破坏性变更升版本。

### 9.2 统一响应（`ApiResponse[T]`，始终 HTTP 200）
所有业务接口统一包装为 `ApiResponse[T]`，**HTTP 状态始终 200**，成败由整数 `code` 区分（`0`=成功）：
```jsonc
{ "code": 0,     "message": "ok",     "data": { /* T：资源 或 分页结构 */ } }   // 成功
{ "code": 33001, "message": "模型不存在", "data": null, "details": {} }            // 失败
```
- 用 Pydantic 泛型 `ApiResponse[T]` 定义，OpenAPI 可描述、orval 可生成类型；前端取 `resp.data`、按 `resp.code` 判错。
- **例外**：`/health` 等探针按真实 HTTP 状态（供 Docker/LB 判活）；SSE 走事件协议（§9.5）。
- **空值规范**：列表空→`[]`、字符串空→`""`、对象不存在→`null`（细则见 standards §6.3）。

### 9.3 错误码体系（按模块分段）
- `code` = 5 位 `M K NNN`：`M`(1位)=模块域(1 公用·2 identity·3 models·4 knowledge·5 tools·6 apps·7 runtime·8 observability)、`K`(1位)=类别(0 参数·1 鉴权·2 权限·3 资源·4 业务·5 限流·9 外部/系统)、`NNN`(3位)=模块内序号。**首位即定位出错模块**。集中登记在 `core/error_codes.py`，每码对应常量名。
- 与 `AppError(code:int, reason, message, http_status=200, details)` 对应，core 中央处理器统一转 §9.2 信封。
- 全量码表见 [standards §6.4](./docs/standards.md)；示例：`33001 MODEL_NOT_FOUND`、`34001 EMBEDDING_DIM_MISMATCH`、`39001 MODEL_AUTH_FAILED`、`19002 EXTERNAL_TIMEOUT`、`19003 CIRCUIT_OPEN`。

### 9.4 分页（混合：游标 / offset）
- **大/追加型**（messages/conversations/traces）：**游标分页** `{ items, next_cursor, has_more }`，游标=`(created_at,id)`。
- **小配置列表**（models/apps/kb/tools/users）：offset `?page=&page_size=`（默认 20）→ `{ items, total, page, page_size }`；**`total` 仅第一页查询返回**，翻页不复查。
- 细则见 standards §5。

### 9.5 流式（SSE）
事件：`message`(token) / `step`(Agent 步骤) / `usage` / `done` / `error`。错误经 `error` 事件下发（不套 `ApiResponse`）。

### 9.6 模块间内部契约（Python）
- 以**类型化 service 函数 + Pydantic DTO** 通信；不跨边界传 ORM。
- 关键 DTO 与签名：
  - `ContentBlock`（联合类型，见 §10.2）。
  - `models.invoke(ref: ModelRef, messages: list[ContentBlock], stream: bool) -> InvokeResult`（`InvokeResult{ content, usage, finish_reason }`）。
  - `models.embed(ref: ModelRef, texts: list[str]) -> list[list[float]]`。
  - `knowledge.retrieve(kb_id, query, top_k=5, threshold=None) -> list[RetrievedChunk]`。
  - `tools.call_tool(tool_id, args: dict) -> ToolResult`；`tools.get_specs(ids) -> list[ToolSpec]`。
  - `observability.trace(type, input, output, metrics, status, **ctx)`。
- **错误契约**：core 定义异常基类 `AppError(code:int, reason, message, http_status=200, details)`，子类 `NotFoundError/ValidationError/PermissionError/ExternalServiceError/RateLimitError/CircuitOpenError`；各模块抛类型化异常，core 处理器统一转 §9.2 信封（始终 HTTP 200，错误码见 §9.3）。

### 9.7 扩展契约（插件机制）
- 新模型厂商：实现 Provider 适配器接口（或纯 LiteLLM 配置）。
- 新工具：实现 `Tool` 协议（`spec() -> ToolSpec`，`call(args) -> ToolResult`），内置/API/MCP 三类统一。

---

## 10. 数据模型（定稿）

**通用约定**：
- **主键**：自增 `bigint`（`generated always as identity`）。对外暴露的资源（如发布分享）另用随机 `share_token`，不直接暴露自增 id。
- **时间戳**：所有表含 `created_at`、`updated_at`（`timestamptz`，UTC）。
- **多工作区预埋**：所有顶层业务表含 `workspace_id`（FK，默认 `default`，UI 不暴露切换）。
- **枚举**：用字符串 + CHECK 约束（迁移友好，胜过 PG enum 的改动成本）。
- **JSON**：用 `JSONB`。
- **删除（选择性软删除，D1=A）**：**配置/用户可见表**（apps/knowledge_bases/models/model_providers/tools/users）含 `deleted_at timestamptz NULL`，软删除可恢复+留痕；查询默认过滤 `deleted_at IS NULL`，**唯一约束改为部分唯一索引** `WHERE deleted_at IS NULL`。**追加型日志/派生表**（traces/messages/conversations/usage_daily/chunks/documents/annotations）物理删除/归档（级联见 FK）。明细分类见 [standards §2](./docs/standards.md)。

> 下表 UNIQUE 标注的配置表，落地时一律实现为"部分唯一索引（`WHERE deleted_at IS NULL`）"以与软删共存。

| 表 | 列（类型 / 约束） |
|---|---|
| `workspaces` | id PK; name text; （种子一条 `default`） |
| `users` | id PK; workspace_id FK→workspaces; email citext **UNIQUE(workspace_id,email)**; password_hash text; role text CHECK in(admin,member) |
| `model_providers` | id PK; workspace_id FK; type text CHECK(openai,anthropic,ollama,openai_compatible); name text; base_url text NULL; credentials_encrypted bytea; enabled bool default true; **UNIQUE(workspace_id,name)** |
| `models` | id PK; workspace_id FK; provider_id FK→model_providers ON DELETE CASCADE; model_key text; type text CHECK(llm,embedding,rerank); capabilities JSONB(default '[]'); embedding_dim int NULL（embedding 模型必填）; default_params JSONB; enabled bool; **UNIQUE(provider_id,model_key)** |
| `apps` | id PK; workspace_id FK; type text CHECK(chat,agent); name text; config JSONB(model_id,system_prompt,params,kb_ids[],tool_ids[],agent_strategy,max_iterations); status text CHECK(draft,published) default draft; share_token text UNIQUE NULL（发布分享用，随机串，非自增 id）; created_by FK→users |
| `knowledge_bases` | id PK; workspace_id FK; name text; embedding_model_id FK→models; config JSONB(chunk_size,overlap,top_k,threshold); **UNIQUE(workspace_id,name)** |
| `documents` | id PK; kb_id FK→knowledge_bases ON DELETE CASCADE; filename text; file_path text; status text CHECK(pending,processing,done,failed) default pending; error text NULL; char_count int default 0 |
| `chunks` | id PK; document_id FK→documents ON DELETE CASCADE; kb_id FK→knowledge_bases; content text; embedding **vector(N)**（N=部署级 embedding 维度，见 §11）; metadata JSONB; position int |
| `tools` | id PK; workspace_id FK; type text CHECK(builtin,api,mcp); name text; schema JSONB; credentials_encrypted bytea NULL; config JSONB; enabled bool; **UNIQUE(workspace_id,name)** |
| `conversations` | id PK; app_id FK→apps ON DELETE CASCADE; workspace_id FK; user_id FK→users NULL; title text |
| `messages` | id PK; conversation_id FK→conversations ON DELETE CASCADE; role text CHECK(user,assistant,system,tool); content **JSONB**(content-blocks，见 §10.2) |
| `traces` | id PK; workspace_id FK; conversation_id FK NULL; message_id FK NULL; app_id FK NULL; type text CHECK(llm_call,tool_call,retrieval,agent_step); input JSONB; output JSONB; tokens_in int; tokens_out int; cost numeric(12,6); latency_ms int; status text; error text NULL |
| `usage_daily`（用量汇总） | id PK; workspace_id FK; day date; app_id FK NULL; model_id FK NULL; tokens_in bigint; tokens_out bigint; cost numeric(14,6); requests int; **UNIQUE(workspace_id,day,app_id,model_id)** |
| `annotations` | id PK; message_id FK→messages ON DELETE CASCADE; label text; note text NULL; created_by FK→users |

### 10.2 消息 content-blocks（多模态/工具统一结构）
`messages.content` = JSONB 数组；内部统一表示，由 `models.invoke` 翻译成各厂商格式：
```json
[
  {"type":"text","text":"这张截图报什么错？"},
  {"type":"image","source":{"kind":"url","url":"..."}},
  {"type":"tool_use","id":"...","name":"http_request","input":{}},
  {"type":"tool_result","tool_use_id":"...","content":[{"type":"text","text":"..."}]}
]
```

---

## 11. 索引策略（定稿）

### 11.1 关系索引
- **所有外键建 btree 索引**：`workspace_id`、`provider_id`、`kb_id`、`document_id`、`conversation_id`、`app_id`、`model_id`、`created_by`。
- **复合索引（按高频查询）**：
  - `apps(workspace_id, type, status)` — 列表筛选
  - `documents(kb_id, status)` — 摄取状态看板
  - `messages(conversation_id, created_at)` — 拉取会话历史
  - `conversations(app_id, created_at desc)` — 会话列表
  - `traces(workspace_id, app_id, created_at desc)` — 可观测查询
  - `chunks(kb_id)` — 检索前置过滤
- **唯一约束**：见 §10 各表 UNIQUE（防重复 provider/kb/tool/用户邮箱）；软删配置表实现为部分唯一索引（`WHERE deleted_at IS NULL`）。
- **软删字段入索引**：软删表的高频复合索引纳入 `deleted_at`（或建部分索引），保证默认过滤走索引。
- JSONB 如需按键查询（如 `models.capabilities` 含 vision）可加 **GIN 索引**；v1 数据量小，按需再加。

> **索引设计规范（必须遵守）**：等值列在前/范围列在后；逻辑删除字段入索引；唯一性用 UNIQUE INDEX 不靠代码层；禁止在大文本字段（`chunks.content` 等）建索引；多对多关联表两向都建索引（本项目 apps 用 JSONB 数组引用，非关联表，不适用）。逐条与核查清单见 [standards §3](./docs/standards.md)。

### 11.2 向量索引（pgvector）
- `chunks.embedding` 用 **HNSW**（pgvector ≥0.5，质量/延迟均衡，免训练），操作符类 **`vector_cosine_ops`**（余弦相似）。
  ```sql
  CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
  ```
  查询期可调 `SET hnsw.ef_search`（默认 40，召回不足时调高）。
- 备选 IVFFlat（需 `lists` 与训练），本项目规模 HNSW 更省心，**默认 HNSW**。
- 检索按 `kb_id` 过滤 + 向量近邻：`WHERE kb_id = :kb ORDER BY embedding <=> :q LIMIT :k`（`<=>` = 余弦距离）。

### 11.3 嵌入维度（重要约束）
pgvector 列维度固定，而不同 embedding 模型维度不同（如 1536 / 1024 / 768）。决策：
- **部署级统一一个 embedding 维度 N**（`core.config` 配置，默认 `1536`，对应常见 embedding 模型）；`chunks.embedding` 即 `vector(N)`。
- `models.embedding_dim` 记录每个 embedding 模型维度；创建知识库时**校验所选 embedding 模型维度 == N**，不匹配则拒绝。
- 想换不同维度模型 = 重建索引/迁移（列入运维注意事项），不在 v1 支持"多维度共存"（YAGNI，避免每维度一张表的复杂度）。

> ✅ 已定稿：embedding 维度默认 **1536** 且全局统一；换维度 = 迁移+重建索引（运维注意），v1 不支持多维度共存。

---

## 12. 性能预判与大表预判（50 人内）

### 12.1 性能预算

| 指标 | 预算 | 说明 |
|---|---|---|
| 峰值并发对话 | ~10–20 | FastAPI 异步胜任 I/O 密集流式 |
| 首 token | < 2s（主要是模型） | 我方编排开销 < 100ms |
| 非 LLM 接口 p95 | < 300ms | CRUD/配置 |
| RAG 检索 | < 200ms（语料 < ~10 万 chunk） | HNSW 索引；超量调 `ef_search`/分区 |
| 文档摄取 | 异步无硬 SLA，前端显进度 | 受 embedding API 限速；限单文件大小 |

**瓶颈认知**：延迟主要来自外部模型 API → 优化重心是 async 不阻塞、重活异步化、向量索引；而非微优化。

### 12.2 大表预判与归档

| 表 | 增长 | 策略 |
|---|---|---|
| `traces` | **最快**（每次调用 1+ 行） | 月分区或定期归档；保留期可配（默认 90 天），过期转冷存/删 |
| `messages` | 较快 | 游标分页；长期按 conversation 归档 |
| `chunks` | 随语料 | <10 万 HNSW 无感；超量分区/独立向量库（§17） |
| `usage_daily` | 慢（每日聚合） | 无需特殊处理 |

**铁律**：大表查询必须走索引 + 限定范围（时间/外键）+ 强制 LIMIT，禁全表扫描与无界排序。细则见 [standards §4](./docs/standards.md)。

## 13. 运维预期（50 人内 / 单人维护）

| 维度 | 生产 | 调试/开发 |
|---|---|---|
| 部署 | 单机 Docker Compose 一键起 | 同左，可跑个人机 |
| 资源 | ~4–8 vCPU / 16GB / 50–100GB | **更低：~2 vCPU / 4–8GB**；LLM 走 API 不吃本机 |
| 备份 | pg_dump 定时 + 文件卷 | 可免 |
| 升级 | `git pull` → `compose up --build` → Alembic 迁移 | 同左 |
| 密钥 | 凭证加密存库 + 部署 `.env` | `.env` 本地 |
| 监控 | 结构化 JSON 日志 + 用量统计 + `/health` 探针；预留 OTel 钩子（D7=A） | 同左 |
| 可用性 | 非 HA，单实例（D6=A：应用无状态、状态外置，可后续水平扩） | — |

## 14. 第一阶段 P0 范围（地基）

**P0 = core 基础层 + identity + models + observability 基线 + 工程骨架**

1. 工程骨架：backend(uv/ruff/mypy/pytest) + alembic + Postgres(pgvector) + Redis + Celery + frontend(vite/ts/antd/orval) + Docker Compose 一键起。
2. **core**：config、db/session/Base、异常体系+处理器、security(加密/哈希/token)、logging、types、pagination。
3. `identity`：登录鉴权、单工作区种子、admin/member。
4. `models`：厂商/凭证(加密)、模型注册表(capabilities/embedding_dim)、`invoke`/`embed` 网关、连通性测试。
5. `observability` 基线：traces 表+记录、用量汇总、health 探针、评估钩子接口(占位)。
6. 可扩展骨架：Provider 适配器接口、`Tool` 协议定义、Celery 任务骨架、`import-linter` 契约。
7. 前端最小：登录、模型配置页、用量/trace 查看页（API 由 orval 生成）。

**完成判据**：控制台配置模型并测连通；经网关发起一次 LLM 调用并在 trace/用量看到记录；`import-linter`/ruff/mypy/pytest 全绿；Compose 一键起。

后续：P1 聊天助手 → P2 RAG → P3 工具 → P4 Agent → P5 可观测深化+评估 →（later）工作流编排。

## 15. 错误处理与测试策略

**错误处理**：core 定义 `AppError` 体系；厂商错误在 `models` 网关捕获归一；异步失败写 `documents.status=failed`+error 可重试；SSE 发 `error` 事件；Pydantic 入口校验；core 中央处理器统一转 `ApiResponse` 信封(§9.2，始终 HTTP 200 + 错误码)。

**测试**：单元(mock 外部) + 集成(测试 Postgres+pgvector、Celery eager) + 检索/评估(fixture KB)；遵循 TDD；`import-linter` 守依赖分层；前端组件冒烟。

---

## 16. 外部调用韧性（超时 / 重试 / 熔断 / 隔离）

所有出网调用（`models.invoke/embed`、`tools.call_tool` 的 api/mcp 类、摄取 embedding）必经 **core 统一的外部调用包装**，集中实现韧性策略；各模块不自行裸调 httpx。具体默认值与可重试错误清单见 [standards §7](./docs/standards.md)。

| 维度 | 设计 |
|---|---|
| **超时** | 连接 5s；读：非流式 30s / 流式 60s / embedding 30s。**禁止无超时调用**（CLAUDE.md 编码准则强制）。 |
| **重试** | 仅可重试错误（连接错误/5xx/429/超时）指数退避+抖动，最多 2 次；4xx 鉴权/参数错误不重试。 |
| **熔断** | 按 **provider 维度**，滑动窗口失败率超阈值→打开，快速失败返回 `19003 CIRCUIT_OPEN`，半开探测恢复。 |
| **隔离（bulkhead）** | 每 provider 独立 httpx 连接池 + 信号量限并发；异步重活走 Celery 独立队列，单个慢厂商不拖垮全局。 |
| **可观测** | 每次外部调用经 `observability.trace` 记录 latency/tokens/status/error。 |

```mermaid
flowchart LR
    CALLER[runtime / knowledge / worker] --> WRAP[core.external_call 包装]
    WRAP --> TO[超时] --> RT[重试] --> CB{熔断?}
    CB -- 打开 --> FAIL[快速失败 50301]
    CB -- 闭合/半开 --> POOL[provider 连接池+信号量] --> EXT[(外部 API)]
    WRAP -.记录.-> OBS[observability.trace]
```

> 实现取舍：v1 用轻量自实现（httpx timeout + tenacity 风格重试 + 简单熔断器 + asyncio.Semaphore），不引入重型韧性框架，符合"不过度抽象/不引栈外重依赖"。

## 17. 可扩展性与演进路径

当前为单机模块化单体；下列扩展点**已在设计中预留接口，无需改业务代码即可演进**（对应评审 D4/D5/D6）：

| 维度 | v1（现在） | 演进路径（按需） | 预留方式 |
|---|---|---|---|
| **向量库**（D4=A） | pgvector + HNSW | Qdrant / Milvus 独立向量库 | `knowledge.retrieve()`/写入抽象成接口，存储可替换 |
| **消息队列**（D5=A） | Celery + Redis | RabbitMQ / Kafka（持久化/广播/有序） | 入队经统一 task 接口封装 |
| **水平扩展 / HA**（D6=A） | 单实例非 HA | 多副本 app + PG 读副本 | 应用无状态、状态全外置（DB/Redis/文件卷） |
| **可观测**（D7=A） | JSON 日志 + 用量 + health | Prometheus + OTel 链路追踪（Tempo/Jaeger） | 日志/调用包装预留 OTel 钩子 |
| **模型/工具** | LiteLLM + Tool 协议 | 新厂商/新工具 | Provider 适配器 + `Tool` 协议（§9.7） |
| **检索质量** | 向量 Top-K | Rerank / 混合检索 | retrieve 后置可插 rerank（迭代版图） |

**原则**：v1 不预先实现这些（YAGNI），但**抽象边界要留对**——切换成本集中在一个 service 接口内，不外溢到业务/前端。

---

## 已定稿决定

**2026-06-26 确认**
1. **主键自增 `bigint`**；对外暴露资源用随机 `share_token`，不暴露自增 id。
2. **embedding 维度默认 1536、全局统一**；换维度 = 迁移+重建索引，v1 不支持多维共存。
3. **取消 `console` 模块**，路由按模块就近 + `main.py` 装配；跨模块复合编排归 `runtime`。
4. **跨模块调用 7 条强约束 + `import-linter` 强制**（§6.3）。
5. **前端接口类型由后端 OpenAPI 经 orval 生成**，不手写（§9）。
6. **向量索引 HNSW + 余弦**（§11.2）。

**2026-06-27 设计评审确认**
7. **D1 选择性软删除**：配置表带 `deleted_at`（部分唯一索引），日志表物理/归档（§10、standards §2）。
8. **D2 混合分页**：大/追加型游标、小列表 offset，`total` 仅首页查询（§9.4、standards §5）。
9. **D3 统一响应 `ApiResponse[T]`**：始终 HTTP 200 + 整数错误码体系（§9.2/§9.3、standards §6）。
10. **D4 向量库 pgvector**、**D5 队列 Celery+Redis**、**D6 单实例非 HA（无状态）**、**D7 可观测=日志+用量+health（预留 OTel）**；演进接口见 §17。
11. **外部调用韧性**：超时/重试/熔断/隔离统一在 core 包装（§16、standards §7）。
12. **工程细则权威文档** `docs/standards.md`（数据/索引/分页/接口/外部调用 + 核查清单）。
