# AGENTS.md — {{PROJECT_NAME}}

> 适用于 Codex CLI 及其他通用 AI 编码工具。Claude Code 用户参考 `CLAUDE.md`。
>
> **进入项目必读**：`.ai/memory/MEMORY.md` → `.ai/memory/user-profile.md` → 开始工作。

---

## 项目简介

{{PROJECT_DESCRIPTION}}

当前状态：{{CURRENT_STATUS}}

---

## 技术栈

| 层 | 技术 |
|---|---|
| {{layer}} | {{tech}} |

---

## 常用命令

```bash
# 启动
{{START_CMD}}

# 测试
{{TEST_CMD}}

# 构建
{{BUILD_CMD}}
```

---

## 行为规则

### 执行风格
- 自主执行，用户授权后不在任务间暂停询问
- 简洁中文响应
- 只在真正 BLOCKED 时停止

### 架构纪律
<!-- 填入本项目的核心约束，详见 .ai/skills/architecture.md -->

### Git
- 提交信息中文，格式：`type(scope): 描述`
- 提交前 `git status` + `git diff` 核对范围
- push 前向用户确认

---

## 关键文档

| 文档 | 用途 |
|---|---|
| `.ai/memory/MEMORY.md` | 记忆索引（必读） |
| `.ai/skills/sdd.md` | SDD 执行方法 |
| `.ai/skills/architecture.md` | 架构纪律 |
| `.ai/framework/skills/code-quality.md` | 编码质量 |
| {{PROJECT_DESIGN_DOC}} | 设计事实来源 |

---

## 如何接手会话

1. 读 `.ai/memory/MEMORY.md`
2. `git log --oneline -10`
3. 读 `.ai/memory/project-state.md`
4. 如有 SDD 任务进行中，读 `.superpowers/sdd/progress.md`
5. 开始工作
