# 功能记忆：聊天助手 (Chat)

## 当前状态

**整体**：🚧 基础完成，体验待打磨

| 子功能 | 状态 | 备注 |
|---|---|---|
| 创建/列出/删除对话 | ✅ | |
| SSE 流式输出 | ✅ | |
| 消息历史展示 | ✅ | |
| 会话 token 计费记录 | ✅ | |
| 系统提示词配置 | ✅ | |
| Markdown 渲染 | ❌ | 前端未做 |
| 停止生成按钮 | ❌ | |
| 消息重试 | ❌ | |
| 多模态输入（图片） | ❌ | DESIGN.md 有规划 |
| 输入框 Shift+Enter 换行 | ❌ | 用户反馈 |

## 关键文件

```
backend/src/agent_hify/modules/chat/
  router.py       # POST /api/v1/conversations/{id}/messages/stream
  service.py      # ChatService.stream_message()
  repository.py
  schemas.py

frontend/src/
  pages/chat/     # 聊天主界面
  components/MessageList/, MessageInput/
```

## 已知问题

- UI 简陋，缺少 Markdown 渲染
- 无停止生成控件
- 输入框不支持 Shift+Enter 换行

## 设计决策

- SSE 端点不用 `str(exc)` 暴露内部错误 → 安全规范，记录 logger.error 后返回固定错误消息

## 接口摘要

```
POST /api/v1/conversations          # 创建对话
GET  /api/v1/conversations          # 列出（分页）
DELETE /api/v1/conversations/{id}   # 删除
POST /api/v1/conversations/{id}/messages/stream  # 流式消息（SSE）
```

## 测试覆盖

- 后端集成测试：覆盖 CRUD + 流式基本路径
- 前端：无自动化测试
