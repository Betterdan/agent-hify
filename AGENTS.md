# AGENTS.md — agent-hify 项目指令

> 适用于 Codex CLI 及其他通用 AI 编码工具。Claude Code 用户请同时参考 `CLAUDE.md`。
>
> **进入项目必读**：先读 `.ai/memory/MEMORY.md`，再读 `.ai/memory/user-profile.md`，再开始工作。

---

## 项目简介

`agent-hify` 是一个 LLM 应用 / Agent 平台（类 Dify，面向 50 人以内团队）。
首要目标：方法论优先，走通"问题界定 → 设计 → 实现 → 评估 → 迭代"完整闭环。

当前状态：P0 功能全部完成（模型管理/聊天/RAG/工具/Agent 循环/可观测），`dev_v1.0.1` 分支进行功能打磨。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · LiteLLM · SQLAlchemy 2.0 + Alembic · Celery + Redis |
| 前端 | Vite + React + TypeScript · Ant Design · TanStack Query |
| 存储 | PostgreSQL 16 + pgvector · Redis |
| 部署 | Docker Compose |

代码组织见 `DESIGN.md §8`；架构依赖层见 `DESIGN.md §5–§6`。

---

## 常用命令

```bash
# 后端开发（在 WSL2 Ubuntu 内执行）
cd /mnt/e/codespace/project/me/agent-hify/backend
DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify \
  uv run uvicorn agent_hify.main:app --reload --port 8000

# 后端测试
DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5433/hify uv run pytest

# 前端
cd /mnt/e/codespace/project/me/agent-hify/frontend
npm run dev          # http://localhost:5173
npm run test
npm run gen:api      # 从 openapi.json 生成类型（orval）

# Docker Compose
cd deploy && docker compose up -d   # 前端 8080，API 8001
```

---

## 行为规则

### 执行风格
- **自主执行**：用户授权后直接开始，不在任务间暂停询问
- **简洁响应**：中文回复，不重复解释已做的事（用户能看 diff）
- 只在真正 BLOCKED（缺少必要信息、不可逆风险）时暂停

### 架构纪律（强约束）
- 只走 service 接口跨模块，禁止 import 其他模块的 `repository.py` / `models.py`
- 跨边界只传 Pydantic DTO 或基本类型
- 依赖单向无环（见 `.ai/skills/architecture.md`）
- `router` 只鉴权 + 校验 + 调 service，不写业务逻辑

### 代码规范
- 不引入技术栈外依赖（需先问用户）
- 所有外部调用必须有超时
- SSE 错误分支：固定字符串 + `logger.error`，不暴露 `str(exc)`
- DB 并发 upsert：`pg_insert ON CONFLICT`，不用 read-then-write
- 前端接口类型由 `orval` 生成，不手写

### Git
- 响应语言：**简体中文**（代码/路径/标识符保持英文）
- 用户已授权 git 写操作（add/commit/push）
- 提交信息中文，格式：`type(scope): 描述`
- 提交前 `git status` + `git diff` 核对范围
- push 前向用户确认

---

## 关键文档

| 文档 | 用途 |
|---|---|
| `DESIGN.md` | 架构设计唯一事实来源 |
| `METHODOLOGY.md` | 项目落地方法论（10 步 + SDD 实践归纳） |
| `.ai/memory/MEMORY.md` | 跨 Agent 记忆索引（必读） |
| `.ai/skills/sdd.md` | SDD 执行方法（有多任务计划时使用） |
| `.ai/skills/architecture.md` | 架构纪律检查清单 |
| `.ai/skills/code-quality.md` | 编码质量标准 |
| `docs/deployment.md` | 部署与体验指南 |
| `docs/standards.md` | 数据表/接口/分页/错误码规范 |

---

## 如何接手会话

1. 读 `.ai/memory/MEMORY.md` 了解当前状态
2. 运行 `git log --oneline -10` 了解最近提交
3. 读 `.ai/memory/project-state.md` 了解当前目标和遗留问题
4. 如果是继续 SDD 任务，读 `.superpowers/sdd/progress.md` 找到下一个未完成任务
5. 开始工作，不需要向用户重新确认已知的上下文
