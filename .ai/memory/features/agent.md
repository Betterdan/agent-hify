# 功能记忆：Agent 执行

## 当前状态

**整体**：✅ P0 完成（手写 ReAct 循环）

| 子功能 | 状态 | 备注 |
|---|---|---|
| ReAct 循环 | ✅ | 手写，不用 LangChain |
| 工具调用路由 | ✅ | |
| 最大步数限制 | ✅ | 防无限循环 |
| 中间步骤 SSE 流 | ✅ | Thought/Action/Observation 实时推送 |
| 前端 Agent 对话界面 | ❌ | 用户反馈功能缺失 |
| 超时控制 | ✅ | 每步有超时 |

## 关键文件

```
backend/src/agent_hify/runtime/
  agent_runner.py    # ReAct 主循环
  tool_dispatcher.py

backend/src/agent_hify/modules/tools/
  (工具注册表)

backend/tests/runtime/
```

## 已知问题

- 前端没有专门的 Agent 对话界面（用户无法体验 Agent 功能）
- Agent 执行结果在聊天界面没有特殊渲染（Thought/Action/Observation 需要特殊展示）

## 设计决策

- Agent 决策循环手写保持透明可控（不用 LangChain/LlamaIndex Agent）
- 跨模块调用只走 runtime 层，不在 agent_runner 里直接 import 其他模块 repository

## 接口摘要

```
POST /api/v1/conversations/{id}/messages/stream
  # 当对话绑定了 tools 时自动走 Agent 路径（SSE 含 type: thought/action/observation/answer）
```

## 测试覆盖

- 后端：ReAct 循环单测、工具调用 mock 测试
