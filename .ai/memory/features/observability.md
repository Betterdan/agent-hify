# 功能记忆：可观测性 (Observability)

## 当前状态

**整体**：✅ P0-9 完成

| 子功能 | 状态 | 备注 |
|---|---|---|
| Trace 追踪（span/event） | ✅ | |
| 用量统计（token 计费） | ✅ | |
| 消息评注 Annotation | ✅ | -1/0/+1 评分 |
| 评估事件 eval_events | ✅ | RAG 命中率等 |
| Trace 过滤/搜索 | ✅ | |
| 前端观测 Dashboard | 🚧 | 基础列表，无图表 |

## 关键文件

```
backend/src/agent_hify/modules/observability/
  router.py
  service.py
  repository.py    # upsert_annotation 用 pg_insert ON CONFLICT
  schemas.py       # rating: -1/0/+1

backend/alembic/versions/
  0007_observability.py    # traces, spans, events, usage
  0008_annotations.py      # annotations (workspace_id, message_id UNIQUE)
  0009_eval_events.py      # eval_events

backend/tests/observability/   # 74 个测试
```

## 已知问题

- 前端只有列表，无可视化图表
- Annotation 评分语义：-1=thumbs-down, 0=neutral, 1=thumbs-up

## 设计决策

- annotation upsert 用 `pg_insert ON CONFLICT DO UPDATE`（原子操作，避免 TOCTOU race condition）
- `upsert_usage` 同样模式

## 接口摘要

```
GET  /api/v1/traces              # 列出（分页+过滤）
GET  /api/v1/traces/{id}         # 详情
POST /api/v1/annotations         # 评注（upsert）
GET  /api/v1/annotations/{message_id}  # 获取评注
GET  /api/v1/usage               # 用量统计
```

## 测试覆盖

- 后端：74 个测试，含 workspace 隔离测试
