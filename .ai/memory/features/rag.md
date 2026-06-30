# 功能记忆：知识库 / RAG

## 当前状态

**整体**：✅ P0 完成

| 子功能 | 状态 | 备注 |
|---|---|---|
| 知识库 CRUD | ✅ | |
| 文件上传（PDF/TXT/MD） | ✅ | |
| 文档解析（LlamaIndex） | ✅ | 只用解析，检索手写 |
| 向量化（pgvector） | ✅ | |
| Celery 异步处理 | ✅ | |
| 混合检索（向量+关键词） | ✅ | |
| 命中率可观测 | ✅ | eval_events 记录 |
| 前端知识库管理界面 | 🚧 | 基础 CRUD UI，体验简陋 |
| 检索结果预览 | ❌ | |

## 关键文件

```
backend/src/agent_hify/modules/knowledge/
  router.py, service.py, repository.py
  parsers/     # 文件解析
  retrieval/   # 手写检索逻辑（混合）

backend/tests/knowledge/
```

## 已知问题

- 前端知识库管理 UI 较简陋

## 设计决策

- 解析用 LlamaIndex，检索手写透明（可控可观测）
- 异步处理走 Celery + Redis，不阻塞上传 API

## 接口摘要

```
POST /api/v1/knowledge-bases          # 创建
POST /api/v1/knowledge-bases/{id}/documents  # 上传文档（触发异步处理）
GET  /api/v1/knowledge-bases/{id}/documents  # 列出文档及处理状态
POST /api/v1/knowledge-bases/{id}/search     # 检索（测试用）
```

## 测试覆盖

- 后端：上传处理流程、检索精度基线
