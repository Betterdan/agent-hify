# 项目状态

> 最后更新：2026-06-30

## 当前分支

`dev_v1.0.1`（从 `dev_v1.0.0` @ 4b6c9ed 切出）

## 已完成（P0 全部完成）

| 阶段 | 内容 | 关键 commit |
|---|---|---|
| P0-1 | 后端骨架（Docker/Alembic/Celery/import-linter） | 初始提交系列 |
| P0-2 | core 横切 + identity 登录鉴权 | — |
| P0-3 | models 模型网关 + observability 基线 + 韧性 | — |
| P0-4 | 前端控制台（Vite+React+TS+orval） | def906e |
| P0-5 | 聊天助手 + SSE 流式 | 77115c2 |
| P0-6 | RAG 知识库 + Celery 摄取 + pgvector | 13c0a2e |
| P0-7 | 工具集成（builtin/api/mcp）| 407c138 |
| P0-8 | ReAct Agent 循环 + step SSE | fd6e057 |
| P0-9 | Annotation 评分 + eval_events + trace 增强 | 0f071ab |

## 当前目标（v1.0.1）

**功能打磨阶段**——基于第一次体验反馈，逐功能点细化讨论后确定优化范围。

当前状态：功能点梳理/讨论中，尚未开始实现。

## 已知遗留问题（来自 P0 Minor 账本）

- ChatPage `lastMsgId` 切换历史会话时不重置
- AgentPage 无 AbortController（流式中无法中止）
- AgentPage step 卡片截断 80 字无省略号
- agent 工具调用中间步骤未持久化到 Message 表（多轮 Agent 会丢失 tool 历史 context）
- RAG 全失败时无 trace 记录
- 知识库上传文档后无自动刷新进度

## 环境速查

```
# 测试 DB
DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify

# 后端开发起
cd backend && DATABASE_URL=... uv run uvicorn agent_hify.main:app --reload --port 8000

# Worker
DATABASE_URL=... REDIS_URL=redis://localhost:6379/0 uv run celery -A agent_hify.worker.celery_app.celery worker -l info

# 前端
cd frontend && npm run dev   # 访问 http://localhost:5173

# Docker Compose（前端 8080，API 8001）
cd deploy && docker compose up -d
```
