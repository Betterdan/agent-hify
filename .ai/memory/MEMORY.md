# Memory Index — agent-hify

> 进入项目时先读本文件。每条记忆有独立文件，这里是索引和快速摘要。

## 用户

- [user-profile.md](user-profile.md) — Dan (Betterdan)，简体中文沟通，WSL2 Ubuntu-26.04 开发

## 行为规范

- [feedback.md](feedback.md) — 从协作历史提炼的 22 条行为规则（执行/代码/安全/架构/Git/沟通）

## 项目状态

- [project-state.md](project-state.md) — dev_v1.0.1 分支，P0 全部完成，v1.0.1 进行功能打磨

## 功能记忆

- [features/auth.md](features/auth.md) — JWT 认证 + workspace 隔离，种子账号 admin@agent-hify.local
- [features/models.md](features/models.md) — 模型/Provider 管理，体验待改善（无下拉枚举、无模型 ID 提示）
- [features/chat.md](features/chat.md) — 聊天助手，SSE 流式完成，UI 简陋（无 Markdown 渲染、无停止按钮）
- [features/rag.md](features/rag.md) — 知识库 + 混合检索，Celery 异步处理，P0 完成
- [features/tools.md](features/tools.md) — 工具集成（MCP + 外部 API），P0 完成
- [features/agent.md](features/agent.md) — 手写 ReAct 循环，前端无专属 Agent 界面
- [features/observability.md](features/observability.md) — Trace/Annotation/用量，P0-9 完成，74 个后端测试

## 关键技术决策速查

| 决策 | 结论 |
|---|---|
| Annotation 并发 upsert | `pg_insert ON CONFLICT DO UPDATE`，不用 read-then-write |
| 模型 ID 格式 | `<provider>/<model-id>`（如 `openai/gpt-4o-mini`，由 LiteLLM 路由） |
| Agent 循环 | 手写 ReAct，不用 LangChain |
| 跨模块调用 | 只走 service 接口，禁止 import 其他模块 repository/models |
| 测试 DB 端口 | 5433（本地 WSL），生产 5432 |
| Docker Compose 端口 | 前端 8080，API 8001（避免与本地 nginx/uvicorn 冲突） |
| 代理配置 | WSL 内可用 127.0.0.1:7897，Docker 容器需开 Allow LAN |
| node_modules 位置 | 软链到 WSL ext4（NTFS TAR 问题），npm 在 WSL 内执行 |
| 错误码范围 | 10000–89999，首位 1–8 |

## 跨项目框架

- 通用框架（可迁移到任何项目）：[.ai/framework/](../framework/)
- 迁移指南：[framework/PORTING.md](../framework/PORTING.md)
