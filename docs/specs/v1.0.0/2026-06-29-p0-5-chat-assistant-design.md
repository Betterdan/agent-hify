# P0-5 聊天助手设计规格

> 版本：v1.0 | 日期：2026-06-29
> 依赖：P0-1~P0-4（骨架 + core + identity + models + observability + 前端控制台）全部完成
> 配套：[DESIGN.md](../../DESIGN.md)（架构总设计）

---

## 1. 目标与范围

### 1.1 目标
实现最小可用的**聊天助手**：用户在控制台创建聊天类应用（配置模型 + 系统提示词），然后在聊天界面与模型进行多轮对话，响应以 SSE 流式返回。

### 1.2 范围（P0-5 内）
- **后端**：`apps` 模块（应用 CRUD）+ `runtime` 模块（对话管理 + 聊天执行 + SSE 流式）
- **前端**：应用列表/创建页、聊天界面（对话列表 + 消息线程 + 流式输入框）
- **不含**：RAG 检索（P0-6）、工具调用（P0-7）、Agent 循环（P0-8）、多模态图片上传 UI（后续迭代）

### 1.3 完成判据
- 创建 chat 类型应用，配置模型 + 系统提示词
- 在聊天界面发送消息，流式显示模型回复
- 多轮对话历史正确维护
- `traces` 和 `usage_daily` 记录每次调用
- 单元 + 集成测试全绿；lint/mypy/import-linter 绿；前端测试 + build 绿

---

## 2. 后端设计

### 2.1 apps 模块（L3）

**数据模型**（迁移新增，表 `apps` 已在 DB 设计中定义）：
```sql
-- 已在 DESIGN.md §10 定义，此处确认字段：
apps:
  id bigint PK
  workspace_id bigint FK→workspaces
  type text CHECK(chat, agent) default 'chat'
  name text NOT NULL
  config jsonb NOT NULL default '{}'
  status text CHECK(draft, published) default 'draft'
  share_token text UNIQUE NULL
  created_by bigint FK→users
  created_at timestamptz
  updated_at timestamptz
  deleted_at timestamptz NULL  -- 软删除
```

**AppConfig（JSONB 结构，P0-5 chat 类型）**：
```json
{
  "model_id": 1,
  "system_prompt": "你是一个有帮助的助手。",
  "params": {
    "temperature": 0.7,
    "max_tokens": 2048
  },
  "kb_ids": [],
  "tool_ids": [],
  "agent_strategy": null,
  "max_iterations": null,
  "history_limit": 20
}
```

**Pydantic Schemas**：
```python
class AppConfigChat(BaseModel):
    model_id: int
    system_prompt: str = ""
    params: dict[str, Any] = Field(default_factory=lambda: {"temperature": 0.7, "max_tokens": 2048})
    history_limit: int = 20  # 载入的最近消息条数

class AppCreate(BaseModel):
    type: Literal["chat", "agent"] = "chat"
    name: str  # 1-100 chars
    config: AppConfigChat  # P0-5 只支持 chat config

class AppUpdate(BaseModel):
    name: str | None = None
    config: AppConfigChat | None = None
    status: Literal["draft", "published"] | None = None

class AppOut(BaseModel):
    id: int
    type: str
    name: str
    config: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime
```

**接口（挂载前缀 `/api/v1`）**：
| 方法 | 路径 | 描述 |
|---|---|---|
| POST | `/apps` | 创建应用 → `AppOut` |
| GET | `/apps` | 列表（offset 分页，`?page=1&page_size=20`）→ `Page[AppOut]` |
| GET | `/apps/{id}` | 获取应用 → `AppOut` |
| PUT | `/apps/{id}` | 更新应用 → `AppOut` |
| DELETE | `/apps/{id}` | 软删除 → `null` |

错误码（`apps` 模块域 = `6`）：
- `60001` APP_NOT_FOUND
- `60002` APP_NAME_DUPLICATE
- `60003` MODEL_NOT_CONFIGURED（model_id 不存在或不可用）

### 2.2 runtime 模块（L4）

**数据模型**：
```sql
conversations:
  id bigint PK
  app_id bigint FK→apps ON DELETE CASCADE
  workspace_id bigint FK→workspaces
  user_id bigint FK→users NULL
  title text default ''
  created_at timestamptz
  updated_at timestamptz

messages:
  id bigint PK
  conversation_id bigint FK→conversations ON DELETE CASCADE
  role text CHECK(user, assistant, system, tool)
  content jsonb NOT NULL  -- content-blocks 数组
  created_at timestamptz
```

**Schemas**：
```python
class ChatInput(BaseModel):
    conversation_id: int | None = None  # None = 新开对话
    message: str  # 用户文字输入（P0-5 只支持文字）

class ConversationOut(BaseModel):
    id: int
    app_id: int
    title: str
    created_at: datetime
    updated_at: datetime

class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: list[dict[str, Any]]  # content-blocks
    created_at: datetime
```

**接口**：
| 方法 | 路径 | 描述 |
|---|---|---|
| POST | `/apps/{app_id}/chat` | 发起对话（SSE 流式） |
| GET | `/apps/{app_id}/conversations` | 对话列表（游标分页）→ `CursorPage[ConversationOut]` |
| GET | `/conversations/{conv_id}/messages` | 消息列表（游标分页）→ `CursorPage[MessageOut]` |

错误码（`runtime` 模块域 = `7`）：
- `70001` CONVERSATION_NOT_FOUND
- `70002` APP_CONV_MISMATCH（对话不属于该应用）
- `70003` MAX_TOKENS_EXCEEDED（history 构建超出模型限制，截断后仍超）
- `79001` STREAM_ERROR（外部模型调用失败，via SSE error 事件）

### 2.3 SSE 流式协议

**端点**：`POST /api/v1/apps/{app_id}/chat`  
**Content-Type** 请求：`application/json`；响应：`text/event-stream`

**事件序列**：
```
event: message
data: {"delta": "你好"}

event: message
data: {"delta": "，我是"}

event: message
data: {"delta": "助手。"}

event: usage
data: {"tokens_in": 25, "tokens_out": 8, "cost": "0.000123"}

event: done
data: {"conversation_id": 42, "message_id": 99}
```

**出错时**（替代 done）：
```
event: error
data: {"code": 79001, "message": "模型调用失败：..."}
```

**规则**：
- `message` 事件每 token（或若干 token）发送一次
- `usage` 和 `done` 在流结束后各发送一次
- 出错时发 `error` 事件并关闭流（不发 done）
- 前端用 `fetch` + `ReadableStream` 而非 `EventSource`（因为需要 POST）

### 2.4 runtime service 执行流程

```
run_chat(app_id, input, current_user) -> AsyncIterator[SSEEvent]:
  1. 获取 app config（model_id, system_prompt, params, history_limit）
  2. 验证 model 存在且 enabled
  3. 若 conversation_id=null: 创建 conversation（title = input.message[:50]）
     否则: 校验 conversation 属于该 app + workspace
  4. 保存用户消息 → messages（role=user, content=[{type:text, text:input.message}]）
  5. 加载最近 history_limit 条历史消息
  6. 构建 messages 列表: [system] + history + [user]
  7. 调用 models.invoke(model_ref, messages, stream=True, params)
  8. 每个 token → yield SSEEvent(type="message", delta=token)
  9. 收集完整响应文本
  10. 保存 assistant 消息 → messages（role=assistant, content=[{type:text, text:full_text}]）
  11. 调用 observability.trace(type="llm_call", ...)
  12. 调用 observability.record_usage(...)
  13. yield SSEEvent(type="usage", ...)
  14. yield SSEEvent(type="done", conversation_id=..., message_id=...)
```

---

## 3. 前端设计

### 3.1 新增路由
| 路径 | 组件 | 描述 |
|---|---|---|
| `/apps` | `AppsPage` | 应用列表 + 创建按钮 |
| `/apps/:id/chat` | `ChatPage` | 聊天界面（对话列表 + 消息线程） |

更新 `routes.tsx`：加入上述两个路由（受 RequireAuth 保护），Layout 菜单加"应用"入口。

### 3.2 AppsPage（`features/apps/`）
- 卡片列表展示所有应用（名称、类型、状态、创建时间）
- "新建应用"按钮 → Modal 表单（名称、模型选择、系统提示词、temperature）
- 点击应用卡片 → 跳转 `/apps/{id}/chat`

### 3.3 ChatPage（`features/chat/`）
- **左侧边栏**：当前应用的对话列表（点击切换），"新对话"按钮
- **主区域**：消息线程（用户/助手气泡），流式字符逐步追加
- **底部输入框**：文字输入 + 发送按钮（发送时禁用，流式结束后恢复）

### 3.4 SSE 客户端实现

前端用 `fetch` + `ReadableStream` 读取 SSE：
```ts
async function* streamChat(appId: number, input: ChatInput): AsyncGenerator<SSEEvent> {
  const res = await fetch(`/api/v1/apps/${appId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json',
                'Authorization': `Bearer ${getToken()}` },
    body: JSON.stringify(input),
  });
  // 按行解析 SSE 格式（event: / data: 行对）
  for await (const line of readLines(res.body!)) { ... }
}
```

封装在 `features/chat/api.ts`，组件用 `useRef` + `useState` 管理流状态。

### 3.5 前端测试
- `AppsPage.test.tsx`：mock GET /apps，渲染应用列表
- `ChatPage.test.tsx`：mock 对话列表 + 消息列表渲染；不测 SSE 流（集成测试范畴）

---

## 4. 测试策略

### 4.1 后端
- **apps 模块单元测试**：service 层 mock repository，测试 CRUD + 软删 + 错误码
- **runtime 模块单元测试**：mock models.invoke + observability，测试 run_chat 流程
- **集成测试（`@pytest.mark.integration`）**：
  - 创建应用 → 发起对话 → 检查 conversation + messages 落库
  - SSE 响应解析（用 httpx 异步读取流）
  - trace + usage_daily 落库验证
- **import-linter**：验证 runtime → apps/models/knowledge/tools/observability（无反向）

### 4.2 前端
- `AppsPage` 冒烟测试（渲染 + mock API）
- `ChatPage` 消息列表渲染测试（mock API，不测 SSE）

---

## 5. 数据库迁移

新增 Alembic migration：创建 `apps`、`conversations`、`messages` 表，含外键、索引（见 DESIGN.md §11）。

索引（按 DESIGN.md §11.1）：
- `conversations(app_id, created_at desc)`
- `messages(conversation_id, created_at)`
- 软删表：`apps(workspace_id, deleted_at)` 部分唯一索引

---

## 6. 设计决策记录

| 决策 | 选择 | 理由 |
|---|---|---|
| SSE 传输方式 | `fetch` + `ReadableStream` | EventSource 不支持 POST；fetch 可携带 Bearer token |
| 新对话触发 | `conversation_id=null` | 无需单独创建对话接口；一次请求原子完成 |
| 历史消息截断 | 最近 `history_limit` 条（默认 20） | 防止超 context window；可按应用配置 |
| 对话标题 | 首条消息前 50 字符 | 简单可用；后续可加 LLM 自动生成标题 |
| P0-5 不含图片上传 UI | 仅文字输入框 | YAGNI；content-blocks 格式已支持 image，UI 后续迭代 |
| apps 软删 | 带 `deleted_at`（配置表） | 遵循 DESIGN.md D1 选择性软删除 |
