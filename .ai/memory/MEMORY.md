# Memory Index

> 进入项目时先读本文件。每条记忆有独立文件，这里是索引和快速摘要。

## 用户

- [user-profile.md](user-profile.md) — Dan，中文沟通，WSL2 主力开发，有代理（7897），倾向自主授权 Agent 执行

## 行为规范（反馈提炼）

- [feedback.md](feedback.md) — 关键行为规则：自主执行/不频繁询问、响应简洁、git 写权限已授权、复杂任务用 opus

## 项目状态

- [project-state.md](project-state.md) — 当前：dev_v1.0.1 分支，P0 全完成，v1.0.1 进行功能打磨（功能点细化讨论中）

## 快速上下文（重要技术决策）

| 决策 | 结论 |
|---|---|
| node_modules 位置 | 软链到 WSL ext4：`~/.npm_modules/agent-hify-frontend`（NTFS TAR 问题） |
| 测试 DB 端口 | `5433`（hify-testdb 容器），生产 Compose 用 `5432`（容器内网） |
| orval openapi 源 | 静态 `frontend/openapi.json` 快照，不依赖运行时 backend |
| Docker Compose 端口 | 前端 `8080`，API `8001`（避免与本地 nginx/uvicorn 冲突） |
| 代理 | Clash 在 Windows 侧，WSL 可用 `127.0.0.1:7897`，Docker 容器需开 Allow LAN |
| 错误码范围 | 10000–89999，首位 1–8 |
| Agent 错误码 | `AGENT_INTERNAL_ERROR = 79001` |
