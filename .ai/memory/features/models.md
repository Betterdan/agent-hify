# 功能记忆：模型管理 (Models)

## 当前状态

**整体**：🚧 基础完成，配置体验待改善

| 子功能 | 状态 | 备注 |
|---|---|---|
| 添加模型 Provider | ✅ | |
| API Key 加密存储 | ✅ | core.security.encrypt/decrypt |
| 连通性测试 | ✅ | |
| 视觉输入标记 | ✅ | |
| Provider 下拉枚举 | ❌ | 用户反馈：不知道怎么填 |
| 预设模型 ID 建议 | ❌ | 用户反馈：格式不明确 |
| 支持 Gemini/Claude | ✅ | LiteLLM 格式：`google/gemini-*`, `anthropic/claude-*` |

## 关键文件

```
backend/src/agent_hify/modules/models/
  router.py       # CRUD + /test-connectivity
  service.py
  schemas.py      # ProviderIn, ModelIn

frontend/src/pages/models/
```

## 已知问题

- 前端无 Provider 类型下拉（用户不知道填 `openai`/`anthropic`/`google`）
- 无模型 ID 提示（正确格式：`openai/gpt-4o`, `anthropic/claude-3-5-haiku-20241022`）
- Docker 容器内连通性测试可能失败（代理在 Windows 侧，容器无法访问 127.0.0.1:7897）

## 设计决策

- 通过 LiteLLM 作为统一网关，格式：`<provider>/<model-id>`
- 凭证不可回读（API 返回屏蔽字符串）

## 接口摘要

```
POST /api/v1/model-providers              # 添加 provider（含 API Key）
POST /api/v1/model-providers/{id}/test    # 连通性测试
GET  /api/v1/models                       # 列出所有模型
POST /api/v1/models                       # 添加模型
```

## 测试覆盖

- 后端：CRUD + 加密解密 + 连通性测试 mock
