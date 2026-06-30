# Skill: Subagent-Driven Development (SDD)

> 通用方法论，不依赖 Claude Code / Codex 任何特定工具。任何支持"派发子任务"的 Agent 工具均可使用。

---

## 什么时候用

有明确的实现计划（plan 文档）且任务数量 ≥ 2 时使用 SDD。

单个小改动直接内联执行，不需要 SDD。

---

## 核心原则

1. **新鲜上下文隔离**：每个任务派发一个独立子 Agent，不继承父 Agent 的历史上下文，只给它完成本任务所需的信息。
2. **评审门控**：实现完成后必须经过评审（spec 符合度 + 代码质量），评审通过才能进入下一任务。
3. **进度账本持久化**：完成一个任务立即写进度账本，防止上下文压缩/会话切换后丢失进度。
4. **持续执行**：无需在任务间暂停询问用户，只在 BLOCKED 或所有任务完成时停止。

---

## 执行流程

```
读计划文件
  ↓
建立进度账本（.superpowers/sdd/progress.md 或 .ai/sdd-progress.md）
  ↓
逐任务循环：
  1. 写任务 Brief（精确描述：文件路径、接口签名、测试要求、提交格式）
  2. 派发实现子 Agent（只给 brief + 必要上下文，不给整个会话历史）
  3. 实现完成 → 写 diff 文件
  4. 派发评审子 Agent（给 diff + brief + 全局约束）
  5. 评审结果处理：
     - Critical / Important → 派发修复子 Agent → 重新评审
     - Minor → 记入账本，继续
     - Approved → 账本记录完成，进入下一任务
  ↓
全部任务完成 → 全分支最终评审
  ↓
修复最终评审 Important 以上问题 → 合并/推送
```

---

## 任务 Brief 写法

Brief 是给实现子 Agent 的唯一信息来源，必须包含：

- **任务背景**（1-2 句，这是整个项目的第几个任务，做什么）
- **要创建/修改的文件**（精确路径）
- **接口定义**（函数签名、Schema 字段、API 路径）
- **测试要求**（写什么测试，预期通过数量）
- **提交格式**（commit message 格式）
- **完成后报告格式**（status / commit SHA / test count / 关注点）

**不要放入**：其他任务的实现细节、历史会话摘要、与本任务无关的代码。

---

## 进度账本格式

路径：`.superpowers/sdd/progress.md` 或 `.ai/sdd-progress.md`

```markdown
# SDD 进度账本

## [Feature Name]

Base commit: <sha7>

- [x] Task 1: <描述> (commit <sha7>, review Approved, N tests)
      Minor (deferred): <具体问题>
- [x] Task 2: <描述> (commit <sha7>, fix <sha7>, N tests)
- [ ] Task 3: <描述> — 进行中
```

---

## 评审标准

评审子 Agent 给出两个独立判定：

**1. Spec 符合度**（✅ / ❌）
- 所有 Brief 要求的功能点是否都实现了？
- 有没有实现 Brief 之外的东西（over-engineering）？

**2. 代码质量**（Approved / Needs Fix）
- Critical：安全漏洞、数据丢失风险、破坏已有功能 → 必须修复，不可继续
- Important：正确性问题、明显性能问题、违反架构约束 → 必须修复
- Minor：风格、优化、小改进 → 记入账本，可延后

---

## 注意事项

- **不要并行派发实现子 Agent**：同一仓库的并发写入会冲突
- **评审子 Agent 独立**：不要让实现者自己评审自己（可以自检，但不可替代独立评审）
- **Minor 不阻塞**：Minor 问题记账本，全分支评审时统一处理
- **进度账本是唯一可靠的状态**：上下文压缩后，账本 + git log 是恢复的基础
- **测试覆盖是必要条件，不是充分条件**：评审要主动打"测试没覆盖的边角路径"

---

## 模型选择建议

| 任务类型 | 推荐模型 |
|---|---|
| 机械实现（1-2 个文件，有完整规范） | 最轻量模型 |
| 多文件集成、需要上下文判断 | 中等模型 |
| 架构设计、复杂调试、全分支评审 | 最强模型（如 Opus） |
| 评审（按 diff 规模） | 中等到最强 |

---

## 本项目实践归纳

来自 P0-5 ～ P0-9 的实际经验（详见 `METHODOLOGY.md §2ter`）：

- SDD 节奏：Task N 实现中，可同步准备 Task N+1 brief，节省 wall-clock
- import-linter 合约变更必须与依赖层变更同一提交
- SSE 异常分支禁止 `str(exc)`，只用固定字符串 + `logger.error`
- DB upsert 用 `pg_insert ON CONFLICT`，不用 read-then-write
- 全分支评审的 Important 问题，派发单个修复子 Agent 处理全部，不要每个问题单独派发
