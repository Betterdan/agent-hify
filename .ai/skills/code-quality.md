# Skill: 编码质量标准（agent-hify 项目扩展）

> 本文件是 `.ai/framework/skills/code-quality.md` 的项目扩展，包含 agent-hify 专属工具链、规范和红线。
> 通用原则见 framework 版本；本文件只记录项目特定内容。
> 实现时遵循，评审时核查。适用于 agent-hify 全栈（FastAPI 后端 + React 前端）。

---

## 通用原则

**YAGNI（不过度设计）**
- 不为假设的未来需求添加功能或抽象
- 三行相似代码优于过早抽象
- 不引入技术栈外的依赖（需先问用户）

**不写多余注释**
- 只注释"为什么"（隐藏约束、细微不变量、特定 bug 的 workaround）
- 不注释"做什么"（代码本身已说明）
- 不写多行注释块或多段 docstring

**小步可测**
- 每个提交都应是一个可独立测试的改动
- TDD：先写失败测试，再写实现，看到绿灯

---

## 后端（FastAPI + Python）

**工具链**：`uv` + `Ruff`（lint+格式化）+ `mypy` + `pytest`

**命名**
- 函数/变量：`snake_case`
- 类：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`

**类型注解**
- 所有公共函数必须有完整类型注解
- 不用 `Any` 除非确实无法具体化
- ORM 模型字段用 `Mapped[T]`（SQLAlchemy 2.0 风格）

**测试**
- 单元测试：mock 外部依赖
- 集成测试：用真实测试 DB（`@pytest.mark.integration`），端口 5433
- 测试文件命名：`test_<module>.py`，函数 `test_<behavior>`
- 跨次运行用随机唯一名称/id 避免数据冲突

**错误处理**
- 只在系统边界（用户输入、外部 API）做校验
- 不为不可能发生的场景加 fallback
- 外部调用超时用 `call_with_resilience`（已有熔断封装）

---

## 前端（React + TypeScript）

**工具链**：ESLint + Prettier + TypeScript strict + Vitest

**类型**
- 接口类型由后端 OpenAPI 经 `orval` 生成，不手写
- 生成文件在 `frontend/src/lib/api/generated/`，不直接修改
- 组件 props 用 `interface`，不用 `type`（一致性）

**组件规范**
- 功能组件 + hooks，不用 class component
- 状态管理：TanStack Query 处理服务端状态，`useState` 处理 UI 状态
- 不在组件里直接 `fetch`，统一走 `features/<module>/api.ts`

**文件组织**
```
features/
  <module>/
    api.ts          # API 调用层（手写或引用 generated）
    <Page>.tsx      # 页面组件
    __tests__/      # 测试文件
```

**测试**
- 每个页面至少一个 smoke test（组件能 render、关键元素存在）
- API 调用用 `vi.spyOn` mock，不发真实请求
- 测试文件必须和被测文件放在同一 feature 目录

---

## 评审时的红线（直接 Critical）

- 暴露内部错误信息到 SSE/API 响应
- 跨模块直接 import repository/models
- 外部调用无超时
- 明文存储 API Key
- 跨工作区数据泄漏（workspace_id 过滤缺失）
- SQL 注入（直接字符串拼接 SQL）

---

## 常见 Important（需修复）

- DB 并发 upsert 用 read-then-write（应改为 `pg_insert ON CONFLICT`）
- 错误码超出 10000–89999 范围
- 新表缺少 `workspace_id` / `created_at` / `updated_at`
- Router 写了业务逻辑或跨模块调用
- 前端直接操作 DOM 而不用 React 状态
- TypeScript `any` 类型滥用

---

## 常见 Minor（记账本，可延后）

- 测试覆盖率低（边角路径未测）
- 组件过大（>200 行考虑拆分）
- 硬编码数值应提取为常量
- 缺少 loading/error 状态处理
- 注释描述了显而易见的事
