# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 项目简介

`agent-hify` 是一个用于**实践并沉淀 Agent 项目方法论**的实验性产品：用方法论驱动，落地一个**类 Dify、面向 50 人内规模**的 LLM 应用 / Agent 平台。**首要目标是方法论优先**——产品可小，但要走通"问题界定 → 设计 → 实现 → 评估 → 迭代"闭环。

第一版硬核：模型管理（含视觉输入）→ 聊天助手 → RAG → 工具集成（MCP + 外部 API）→ Agent → 可观测基线 + 评估钩子。**工作流编排不在第一版**（阶段性大件）。

## 关键文档（动手前先读）

| 文档 | 作用 |
|---|---|
| [DESIGN.md](./DESIGN.md) | **设计唯一事实来源**：架构、模块依赖、数据流、数据模型、接口规范、性能、运维、P0 范围 |
| [METHODOLOGY.md](./METHODOLOGY.md) | 项目落地方法论（10 步流程），由项目所有者定义、随实践更新 |
| [docs/competitive-brief-agent-platforms.md](./docs/competitive-brief-agent-platforms.md) | 竞品调研结论 |

## 技术栈

- **后端**：FastAPI · LiteLLM(模型网关) · SQLAlchemy 2.0 + Alembic · PostgreSQL + pgvector · Celery + Redis · LlamaIndex(仅解析) + 手写检索 · 手写 Agent 循环 · MCP Python SDK
- **前端**：Vite + TypeScript + React · Ant Design · TanStack Query · React Router · SSE
- **部署**：单机 Docker Compose
- **编码规范**：后端 `uv` + `Ruff`(lint+格式化) + `mypy` + `pytest`，`import-linter` 强制模块依赖分层；前端 ESLint + Prettier + TS strict，接口类型由后端 OpenAPI 经 `orval` 生成（勿手写）。
- 代码组织见 DESIGN.md §8；架构/依赖分层见 §5–§6。

## 常用命令

> 工程尚未脚手架（处于架构设计末尾、即将进入工程搭建）。以下为**规划中的命令**，P0 脚手架落地后据实更新本节：
- 起全套：`docker compose -f deploy/docker-compose.yml up --build`
- 后端测试：`cd backend && pytest`（单测）/ `pytest -k <name>`（单个）
- 迁移：`cd backend && alembic upgrade head` / `alembic revision --autogenerate -m "<msg>"`
- 前端开发：`cd frontend && npm run dev`

---

## 行为指令（实现与协作规则）

### 方法论
- **遵循 [METHODOLOGY.md](./METHODOLOGY.md) 的 10 步流程**。当前进度：架构设计→即将工程搭建。
- **定时归纳方法论**：每完成一个阶段（工程搭建/各功能阶段/测试/部署），或出现可复用的方法论洞见时，把它**增量归纳更新进 METHODOLOGY.md**。是"归纳实际发生的过程"，不是杜撰；**方法论最终由项目所有者定稿**，Claude 只整理。
- **方法论由用户定义**，尤其是"评估的具体方法与指标"——不要替用户发明，只预留接口（见 observability 评估钩子）。

### 设计与实现
- **DESIGN.md 是设计事实来源**；若实现需偏离设计，先更新 DESIGN.md 再动代码。
- **分阶段实现，P0 先行**；一个阶段 = spec → plan → 实现 → 评估。阶段顺序见 DESIGN.md §12。
- **TDD**：实现前先写测试（superpowers test-driven-development）。
- **轮子复用 + 要害手写透明**：模型/解析用成熟库；Agent 决策、检索、评估手写保持可见可控。

### 架构纪律（强约束，详见 DESIGN.md §6.3）
- **只走 service 接口**：禁止 import 其他模块的 `repository.py`/`models.py`(ORM) 或直接访问其表。
- **跨边界只传 DTO**：参数/返回只用 Pydantic schema 或基本类型，不传 ORM 实例。
- **依赖单向无环**：只能依赖更底层模块（分层见 §6.1），唯一例外是任何模块可向下调用 `observability`；`import-linter` 在 CI 强制。
- **横切归 core**：配置/异常/DB/安全/日志/公共类型统一在 `core`，不各造一套。
- **路由薄**：`router` 只鉴权+校验+调本模块 service，不写业务、不跨模块编排；跨模块编排只在 `runtime`。
- **模块内部分层**：`router → service → repository`，`schemas`(DTO)/`models`(ORM) 分离（DESIGN.md §8）。
- **单工作区但始终携带 `workspace_id`**（预埋多工作区，UI 不暴露切换）。
- **接口遵循 DESIGN.md §9**（OpenAPI 单一事实来源、错误信封、分页、SSE 事件、内部契约）。

### 编码准则（DESIGN.md / docs/standards.md 为细则事实来源）
- **写代码时**：不引入不必要的设计模式、不做过度抽象；不引入技术栈以外的依赖（需要时先问用户）；**所有外部调用必须有超时设置**（详见 DESIGN.md 外部调用韧性）。
- **改代码时**：先理解相关模块的设计意图；不为新功能破坏已有接口契约；改完确保已有测试通过。
- **不确定时**：架构选择给 2–3 个方案对比，由用户拍板；规范没覆盖的情况先问用户，不自己编规矩。
- **重复行为提议设 skill**：发现某操作是重复指令、或属于可定义可参照的重复行为时，先提议让用户决定是否定义为 skill。
- 数据表/索引/分页/空值/错误码等规范遵循 `docs/standards.md`；新增表/接口按其核查（可用 `schema-review` skill）。

### 协作约束
- **Git**：用户已授权 Claude 在**本项目**执行 git 写操作（add/commit/push）。提交信息用中文，遵循现有提交风格；提交前先 `git status`/`git diff` 核对范围，不擅自提交无关改动；如在默认分支 `main` 上则先建分支。push 等外发操作前向用户确认。
- **响应语言**：简体中文（代码、文件路径、标识符保持英文原文）。
- 临时文件用 scratchpad，不污染项目目录。
