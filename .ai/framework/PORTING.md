# 如何将此框架迁移到新项目

> 本指南让你在 10 分钟内把 AI 协作框架初始化到任何新项目。

---

## 第一步：复制框架核心

将 `.ai/framework/` 整体复制到新项目：

```bash
cp -r /path/to/agent-hify/.ai/framework /path/to/new-project/.ai/framework
```

同时复制通用记忆（同一个用户在所有项目里共享）：

```bash
cp /path/to/agent-hify/.ai/memory/user-profile.md /path/to/new-project/.ai/memory/
cp /path/to/agent-hify/.ai/memory/feedback.md     /path/to/new-project/.ai/memory/
```

---

## 第二步：初始化项目专属文件

从模板创建：

```bash
cd /path/to/new-project/.ai

# 记忆索引
cp framework/templates/MEMORY.md.tpl       memory/MEMORY.md

# 项目状态
cp framework/templates/project-state.md.tpl memory/project-state.md

# 每个核心功能创建一个 feature 记忆文件
cp framework/templates/feature.md.tpl      memory/features/feature-name.md
```

---

## 第三步：填写项目专属内容

需要人工填写（或让 Agent 帮你填）：

| 文件 | 需要填写的内容 |
|---|---|
| `memory/project-state.md` | 项目名、技术栈、当前分支、里程碑目标 |
| `memory/features/*.md` | 各功能点现状、已知问题、设计决策 |
| `skills/architecture.md` | 本项目的模块边界、依赖规则、数据规范 |
| `AGENTS.md`（根目录） | 本项目的命令、行为规则（从 `framework/templates/AGENTS.md.tpl` 复制改写）|
| `CLAUDE.md`（根目录） | Claude Code 专属指令 |

---

## 第四步：创建项目专属 skills

```bash
# 复制模板，按本项目架构填写
cp /path/to/agent-hify/.ai/skills/architecture.md .ai/skills/architecture.md
# 然后修改其中的模块名称、依赖层级、数据规范
```

通用 skills（`framework/skills/`）无需修改，直接使用。

---

## 第五步：更新根目录入口文件

创建 `AGENTS.md`（Codex CLI 用）和 `CLAUDE.md`（Claude Code 用），两者都应：
1. 引用 `.ai/memory/MEMORY.md`（让 Agent 知道去哪里读记忆）
2. 引用 `.ai/skills/`（让 Agent 知道执行规范在哪）
3. 写明项目专属命令（启动、测试、构建）

---

## 框架文件说明

| 文件 | 类型 | 说明 |
|---|---|---|
| `framework/skills/sdd.md` | 通用 | Subagent-Driven Development 方法论 |
| `framework/skills/code-quality.md` | 通用 | 编码质量原则（语言无关） |
| `framework/templates/*.tpl` | 模板 | 各类文件的初始化模板 |
| `memory/user-profile.md` | 用户级 | 同一用户跨项目可复用 |
| `memory/feedback.md` | 用户级 | 同一用户跨项目可复用 |
| `memory/project-state.md` | 项目级 | 每个项目单独维护 |
| `memory/features/*.md` | 项目级 | 每个项目单独维护 |
| `skills/architecture.md` | 项目级 | 每个项目单独写 |

---

## 后续维护

- **通用 skills 有改进** → 更新 `framework/skills/`，各项目按需同步
- **用户偏好有变化** → 更新 `memory/feedback.md`，可同步到其他项目
- **新功能上线** → 在 `memory/features/` 新建对应文件，更新 `MEMORY.md` 索引
- **阶段方法论归纳** → 更新 `docs/methodology/` 下对应文件
