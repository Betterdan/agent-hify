# Skill: Subagent-Driven Development (SDD)

> 通用方法论，不依赖 Claude Code / Codex 任何特定工具。
> 任何支持"派发子任务"的 Agent 工具均可使用。
> 项目特定的实践归纳见 `docs/methodology/learnings/`。

---

## 适用场景

有明确实现计划（plan 文档）且任务数量 ≥ 2 时使用 SDD。
单个改动直接内联执行，不需要 SDD。

---

## 核心原则

1. **新鲜上下文隔离** — 每个任务派发独立子 Agent，不继承父 Agent 历史，只给完成本任务所需的信息
2. **评审门控** — 实现完成后必须通过独立评审（spec 符合度 + 代码质量），评审通过才进入下一任务
3. **进度账本持久化** — 完成一个任务立即写账本，防止上下文压缩/会话切换后丢失进度
4. **持续执行** — 无需在任务间暂停询问用户，只在 BLOCKED 或所有任务完成时停止

---

## 执行流程

```
读计划文件
  ↓
建立进度账本（路径见各项目约定）
  ↓
逐任务循环：
  1. 写任务 Brief
  2. 派发实现子 Agent（只给 brief + 必要上下文）
  3. 实现完成 → 生成 diff
  4. 派发评审子 Agent（diff + brief + 项目全局约束）
  5. 评审处理：
       Critical/Important → 派发修复子 Agent → 重新评审
       Minor             → 记入账本，继续下一任务
       Approved          → 账本标记完成，进入下一任务
  ↓
全部完成 → 全分支最终评审
  ↓
修复 Important 以上 → 合并/推送
```

---

## 任务 Brief 必须包含

- 任务背景（1-2 句，在整个计划里的位置）
- 要创建/修改的文件（精确路径）
- 接口定义（函数签名、Schema、API 路径）
- 测试要求（写什么测试，预期通过数）
- 提交格式
- 完成后报告格式（status / SHA / test count / 关注点）

**不要放入** — 其他任务的实现细节、历史会话摘要、无关代码。

---

## 进度账本格式

```markdown
# [Feature] SDD 进度

Base commit: <sha7>

- [x] Task 1: <描述> (commit <sha7>, review Approved, N tests)
      Minor: <deferred issues>
- [x] Task 2: <描述> (commit <sha7>, fix <sha7>)
- [ ] Task 3: 进行中
```

---

## 评审标准

**Spec 符合度**（✅/❌）
- 所有 Brief 要求是否都实现？
- 有无实现 Brief 之外的内容（over-engineering）？

**代码质量**（Approved / Needs Fix）
- Critical — 安全漏洞、数据丢失风险、破坏已有功能 → 必须修复，阻塞继续
- Important — 正确性问题、架构违规、明显性能问题 → 必须修复
- Minor — 风格、小优化 → 记账本，可延后

---

## 关键注意事项

- 不并行派发实现子 Agent（同仓库并发写入会冲突）
- 评审子 Agent 必须独立于实现者
- 全分支评审的 Important 问题，用单个修复子 Agent 处理所有问题（不要一问题一 Agent）
- 测试绿灯是必要条件，不是充分条件（评审要主动打未覆盖的边角路径）

---

## 模型选择建议

| 任务 | 模型 |
|---|---|
| 机械实现（完整规范，1-2 文件） | 最轻量 |
| 多文件集成、需要判断 | 中等 |
| 架构设计、复杂调试、全分支评审 | 最强（如 Opus） |
