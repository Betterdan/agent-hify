# 部署与体验指南

> 本文档面向项目开发者/本地体验者。生产部署未做专项加固，不建议直接对公网开放。

---

## 选择哪种方式？

| 方式 | 适合场景 | 前提 |
|---|---|---|
| **方式 A：开发模式**（推荐先用） | 本地快速体验、功能调试、迭代开发 | WSL2 内已有 Python(uv)、Node、PostgreSQL、Redis |
| **方式 B：Docker Compose** | 接近生产的完整镜像验证、干净环境复现 | WSL2 内已安装 Docker Engine |

两种方式选一种即可，不需要都操作。

---

## 方式 A：开发模式（WSL 内直接起进程）

> 所有命令在 WSL2 Ubuntu 终端内执行。Windows 侧打开 WSL 终端：`wsl -d Ubuntu-26.04`

### 前提检查

```bash
# 确认 PostgreSQL 在 5433 端口可用（项目测试库）
psql postgresql://hify:hify@localhost:5433/hify -c "SELECT 1"

# 确认 Redis 可用
redis-cli ping   # 应输出 PONG

# 确认 uv 可用
uv --version

# 确认 Node 可用（v20+）
node --version
```

### 步骤 1：初始化数据库（仅首次）

```bash
cd /mnt/e/codespace/project/me/agent-hify/backend

DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify \
  uv run alembic upgrade head
```

迁移完成后会自动创建种子数据：
- 默认工作区 `default`
- 管理员账号：`admin@agent-hify.local` / `admin123`

### 步骤 2：启动后端 API（终端 1）

```bash
cd /mnt/e/codespace/project/me/agent-hify/backend

DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify \
  uv run uvicorn agent_hify.main:app --reload --port 8000
```

启动后访问 API 文档：http://localhost:8000/docs

### 步骤 3：启动 Celery Worker（终端 2）

> 知识库文档摄取（RAG 功能）需要 Celery，其他功能不依赖它。如果只体验聊天/Agent，可跳过。

```bash
cd /mnt/e/codespace/project/me/agent-hify/backend

DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify \
REDIS_URL=redis://localhost:6379/0 \
  uv run celery -A agent_hify.worker.celery_app.celery worker -l info
```

### 步骤 4：启动前端（终端 3）

```bash
cd /mnt/e/codespace/project/me/agent-hify/frontend
npm run dev
```

前端默认运行在 http://localhost:5173，自动代理 `/api/` 到后端 8000 端口。

### 访问

浏览器打开 **http://localhost:5173**，用以下账号登录：

| 字段 | 值 |
|---|---|
| 邮箱 | `admin@agent-hify.local` |
| 密码 | `admin123` |

---

## 方式 B：Docker Compose

> 在 WSL2 内操作，需要已安装 Docker Engine（`docker --version` 可用）。

### 步骤 1：配置环境变量

```bash
cd /mnt/e/codespace/project/me/agent-hify/deploy
cp .env.example .env
```

`.env` 最小配置（`.env.example` 已包含，直接复制即可本地使用）：

```dotenv
POSTGRES_USER=hify
POSTGRES_PASSWORD=hify
POSTGRES_DB=hify
DATABASE_URL=postgresql+psycopg://hify:hify@postgres:5432/hify
REDIS_URL=redis://redis:6379/0
```

> 生产环境需额外设置 `SECRET_KEY`（随机32字符）和 `ENCRYPTION_KEY`（Fernet key）。
> 本地体验使用 `core/config.py` 中的硬编码默认值即可。

### 步骤 2：构建并启动

```bash
cd /mnt/e/codespace/project/me/agent-hify/deploy
docker compose up --build
```

服务启动顺序：postgres → migrate（自动建表+种子数据）→ redis → api + worker → web(nginx)。
首次构建耗时约 3–5 分钟（下载镜像 + 编译依赖）。

### 步骤 3：访问

浏览器打开 **http://localhost**（nginx 80 端口），用相同账号登录。

### 常用操作

```bash
# 查看日志
docker compose logs -f api
docker compose logs -f worker

# 停止（保留数据）
docker compose stop

# 彻底清除（含数据库 volume）
docker compose down -v
```

---

## 首次使用：必须先配置模型 Provider

登录后，**所有聊天/Agent 功能都需要先配置模型**，否则返回错误。

### 1. 进入模型配置页

左侧菜单 → **模型配置**（或访问 `/models`）

### 2. 添加 Provider

点击「添加 Provider」，填入：

| 字段 | 示例值 |
|---|---|
| 名称 | `OpenAI` |
| Provider 类型 | `openai` |
| API Key | `sk-xxxxx`（你的真实 Key） |
| Base URL | 留空使用默认；使用代理填 `https://your-proxy/v1` |

点击「测试连通性」验证 Key 可用。

### 3. 注册模型

在 Provider 下注册一个具体模型，例如：

| 字段 | 值 |
|---|---|
| 模型 ID（LiteLLM 格式） | `openai/gpt-4o-mini` |
| 显示名称 | `GPT-4o Mini` |
| 是否支持视觉 | 按实际选 |

---

## 功能体验路径

按以下顺序体验，每步依赖上一步：

```
配置模型 → 创建应用 → 聊天 → （选）知识库 → （选）工具 → Agent
```

| 步骤 | 页面 | 操作 |
|---|---|---|
| 1 | **模型配置** `/models` | 添加 Provider + 注册模型 |
| 2 | **应用管理** `/apps` | 点「新建应用」，类型选 `chat`，绑定模型 |
| 3 | **聊天** `/apps/:id/chat` | 发消息，观察 SSE 流式回复；消息下方有 👍👎 评分按钮 |
| 4 | **知识库** `/knowledge` | 新建知识库 → 上传文档（Celery 后台摄取）→ 在应用配置中加 `kb_ids` |
| 5 | **工具** `/tools` | 添加内置工具（如 `datetime`）或 API 工具 |
| 6 | **Agent 应用** `/apps` | 新建应用，类型选 `agent`，绑定模型 + 工具 |
| 7 | **Agent 执行** `/apps/:id/run` | 发消息，观察工具调用 step 卡片 + 最终回答 |
| 8 | **可观测** `/observability` | 查看 trace 列表（状态/延迟/错误）和用量统计 |

---

## 环境变量说明

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://hify:hify@localhost:5432/hify` | PostgreSQL 连接串 |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接串（Celery broker + result） |
| `SECRET_KEY` | `dev-secret-hify-jwt-key-32bytes!` | JWT 签名密钥，**生产必须替换** |
| `ENCRYPTION_KEY` | （见 config.py）| Fernet 对称加密密钥（用于加密 Provider API Key） |
| `EMBEDDING_DIM` | `1536` | 向量维度，需与所用 embedding 模型一致 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT 过期时间（分钟），默认 24 小时 |

> 开发模式下所有变量都有合理默认值，只需在命令行传 `DATABASE_URL` 和 `REDIS_URL`。

---

## 常见问题

**Q：迁移报错 `relation already exists`**

数据库已存在旧表，通常是重复执行 `upgrade head`。先检查当前版本：
```bash
DATABASE_URL=... uv run alembic current
```
已是最新版本则无需处理；若版本混乱可 `drop schema public cascade` 后重跑（**会清空数据**）。

**Q：聊天报错 `litellm.exceptions.AuthenticationError`**

模型 Provider 的 API Key 无效或未配置。回到模型配置页重新填写并测试。

**Q：知识库上传后文档一直显示"处理中"**

Celery Worker 未启动，或 Redis 不可用。检查终端 2（Worker 进程）的日志。

**Q：前端报 `Proxy error`**

后端未启动（终端 1），或端口冲突（8000 被占用）。检查后端日志。

**Q：Docker Compose 构建失败，`uv.lock` 相关报错**

确认 `uv.lock` 已提交到仓库（`git ls-files backend/uv.lock`）。若不存在，在 backend 目录执行 `uv lock` 后提交。
