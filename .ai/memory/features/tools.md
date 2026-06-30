# 功能记忆：工具集成 (Tools)

## 当前状态

**整体**：✅ P0 完成

| 子功能 | 状态 | 备注 |
|---|---|---|
| 内置工具注册 | ✅ | |
| MCP 工具接入 | ✅ | MCP Python SDK |
| 外部 API 工具 | ✅ | |
| 工具超时保护 | ✅ | |
| 工具列表 API | ✅ | |
| 前端工具管理界面 | 🚧 | 基础 UI |

## 关键文件

```
backend/src/agent_hify/modules/tools/
  router.py
  service.py
  mcp_client.py    # MCP SDK 封装

backend/tests/tools/
```

## 已知问题

- MCP 工具需要本地 MCP Server 运行，配置对用户不友好

## 设计决策

- 所有工具调用有超时设置（不能因工具挂起阻塞整个 Agent）
- MCP 工具通过 MCP Python SDK 动态发现

## 接口摘要

```
GET  /api/v1/tools               # 列出可用工具
POST /api/v1/tools               # 注册外部工具
POST /api/v1/tools/mcp           # 注册 MCP Server
```

## 测试覆盖

- 后端：工具注册、调用 mock、超时测试
