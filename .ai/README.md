# .ai/ — 跨 Agent 知识框架

本目录是 **agent-agnostic** 的项目知识库，不依赖任何特定 AI 编码工具。

无论你是 Claude Code、Codex CLI、Cursor 还是其他工具，进入这个项目时都应先读本目录。

## 目录结构

```
.ai/
  README.md          ← 本文件，框架说明
  memory/
    MEMORY.md        ← 记忆索引（入口，先读这里）
    user-profile.md  ← 用户 Dan 的背景、偏好、工作方式
    feedback.md      ← 从历史协作中提炼的行为规范
    project-state.md ← 当前项目状态（比 git log 更有语境）
  skills/
    sdd.md           ← Subagent-Driven Development（核心执行方法论）
    architecture.md  ← 架构纪律（模块边界、依赖规则）
    code-quality.md  ← 编码质量标准
```

## 使用方式

**进入项目时**（每次会话开始）：
1. 读 `.ai/memory/MEMORY.md`（了解用户和项目当前状态）
2. 读 `.ai/memory/user-profile.md`（调整沟通风格）
3. 根据任务类型按需读 `.ai/skills/` 对应文件

**执行开发任务时**：
- 参考 `.ai/skills/sdd.md` 决定执行模式
- 参考 `.ai/skills/architecture.md` 检查代码合规性
- 有架构变更时先改 `DESIGN.md` 再动代码

**更新记忆时**：
- 用户有新的反馈 → 追加到 `.ai/memory/feedback.md`
- 项目状态变化 → 更新 `.ai/memory/project-state.md`
- 记忆索引随时保持最新 → `.ai/memory/MEMORY.md`

## 与工具专属配置的关系

| 文件 | 用途 | 读取方 |
|---|---|---|
| `CLAUDE.md` | Claude Code 专属指令 | Claude Code |
| `AGENTS.md` | Codex CLI 专属指令 | Codex CLI |
| `.ai/` | 所有工具共享知识 | 所有 Agent |

工具专属文件（CLAUDE.md / AGENTS.md）只写**该工具特有的行为**，通用知识统一在 `.ai/` 维护，避免重复。
