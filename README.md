# agent-hify

> 用方法论驱动，落地一个**类 Dify、面向 50 人内规模**的 LLM 应用 / Agent 平台。首要目标是方法论优先——产品可小，但要走通「问题界定 → 设计 → 实现 → 评估 → 迭代」闭环。

## 功能

- **模型管理**：多 Provider（OpenAI / Anthropic / 兼容接口）+ 连通性检测 + 加密存储 API Key
- **聊天助手**：SSE 流式回复 + 多轮对话 + 消息评分（👍👎）
- **RAG 知识库**：文档上传 → Celery 后台摄取 → pgvector 语义检索
- **工具集成**：内置工具 / 外部 API / MCP 协议
- **Agent 循环**：ReAct function-calling，step 事件实时可见
- **可观测**：trace 查询（状态/延迟/错误）+ 用量统计 + 评估钩子

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · LiteLLM · SQLAlchemy 2.0 + Alembic · Celery + Redis |
| 存储 | PostgreSQL 16 + pgvector · Redis |
| 前端 | Vite + React + TypeScript · Ant Design · TanStack Query |
| 部署 | Docker Compose（单机） |

## 快速开始

**详细步骤见 [docs/deployment.md](docs/deployment.md)**，以下是最短路径：

```bash
# WSL2 Ubuntu 内执行

# 1. 初始化数据库（首次）
cd /mnt/e/codespace/project/me/agent-hify/backend
DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify \
  uv run alembic upgrade head

# 2. 启动后端
DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify \
  uv run uvicorn agent_hify.main:app --reload --port 8000

# 3. 启动 Worker（知识库功能需要）
DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify \
REDIS_URL=redis://localhost:6379/0 \
  uv run celery -A agent_hify.worker.celery_app.celery worker -l info

# 4. 启动前端
cd /mnt/e/codespace/project/me/agent-hify/frontend
npm run dev
```

访问 http://localhost:5173，账号：`admin@agent-hify.local` / `admin123`

> 登录后**必须先在「模型配置」页添加 Provider 并注册模型**，聊天/Agent 功能才可用。

## 常用命令

```bash
# 后端测试
cd backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify uv run pytest

# 后端 lint / 类型检查
cd backend && uv run ruff check . && uv run mypy src/

# 前端测试 / lint / 构建
cd frontend && npm run test && npm run lint && npm run build

# Docker Compose（需 Docker）
cd deploy && cp .env.example .env && docker compose up --build
```

## 文档

| 文档 | 说明 |
|---|---|
| [DESIGN.md](DESIGN.md) | 架构设计（唯一事实来源） |
| [METHODOLOGY.md](METHODOLOGY.md) | 项目落地方法论（10 步流程 + 实践归纳） |
| [docs/deployment.md](docs/deployment.md) | 部署与体验指南 |
| [docs/standards.md](docs/standards.md) | 编码规范（表/接口/分页/错误码） |
| [docs/competitive-brief-agent-platforms.md](docs/competitive-brief-agent-platforms.md) | 竞品调研 |
