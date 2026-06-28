# 项目进度与跨环境接续（STATUS）

> 本文件**随 git 跟踪并 push**，是跨环境/跨会话接续的事实来源。
> SDD 账本 `.superpowers/sdd/progress.md` 与 `~/.claude` 记忆是**本机本地、被 git 忽略、不会跟随仓库**——
> 换环境后以本文件 + git history + `docs/superpowers/plans/` 计划为准。
> 最后更新：2026-06-28。当前分支 `dev_v1.0.0`，远端 `origin/dev_v1.0.0`，HEAD = `de7ae47`（已 push）。

## 1. 当前状态（TL;DR）
- **P0-1 后端骨架 ✅ / P0-2 core+identity ✅ / P0-3 models+observability ✅**，全部已 push 到 `origin/dev_v1.0.0`。
- **下一步 = P0-4 前端控制台**（尚未开始；计划见 §5）。
- 新环境接续：`git pull` 拿到全部后端代码与 P0-4 计划；按 §3 搭好基础环境；按 §5 开始 P0-4。

## 2. 提交地图（均在 origin/dev_v1.0.0）
| 阶段 | 范围 | 内容 |
|---|---|---|
| 设计 | …→7544748 | DESIGN v0.5 / docs/standards.md / CLAUDE.md / 四份 P0 计划 |
| P0-1 | `7544748..6c52071` | 后端骨架：Docker/Alembic+pgvector/Celery/import-linter，一键起 |
| P0-2 | `6c52071..f9afc33` | core 横切（统一响应/错误码/异常/分页/security）+ identity 登录鉴权；总评审整改 f9afc33 |
| — | `98e496a` | METHODOLOGY v0.3（§2bis 批量实现+总评审纪律） |
| P0-3 | `98e496a..de7ae47` | models 模型网关 + observability 基线 + core 外部调用韧性；实现 51d4dfd + 总评审整改 de7ae47 |

## 3. 基础环境要求（新环境从零跑通后端）
**后端**：Python ≥ 3.12 + [`uv`](https://docs.astral.sh/uv/)。
```bash
cd backend && uv sync            # 装依赖（含 litellm，~百个传递依赖，首次较久）
```
**测试数据库**：PostgreSQL + pgvector（pg16）。后端默认连 `localhost:5432`（见 `core/config.py`）。
- 若本机 5432 空闲：直接起容器映射 5432，**无需** 设 `DATABASE_URL`：
  ```bash
  docker run -d --name hify-testdb -e POSTGRES_USER=hify -e POSTGRES_PASSWORD=hify \
    -e POSTGRES_DB=hify -p 5432:5432 pgvector/pgvector:pg16
  cd backend && uv run alembic upgrade head     # 应用 0001..0004 迁移
  ```
- 若 5432 被占用（如原作者机器被其它项目 db-postgres-1/db-redis-1 占用，故用 **5433**）：映射到空闲端口并覆盖：
  ```bash
  docker run -d --name hify-testdb ... -p 5433:5432 pgvector/pgvector:pg16
  export DATABASE_URL="postgresql+psycopg://hify:hify@localhost:5433/hify"
  cd backend && uv run alembic upgrade head
  ```
- 种子：迁移 0002 已植入管理员 `admin@agent-hify.local` / `admin123`（集成测试依赖）。
- dev 默认密钥（`encryption_key`/`secret_key`）在 `core/config.py`，**生产须用环境变量覆盖**（部署阶段处理）。

**前端**：Node ≥ 20 + npm（原机 Node 22.19.0 / npm 10.9.3）。`frontend/` **尚未脚手架**，由 P0-4 创建。

**全栈一键起**（部署/联调）：`docker compose -f deploy/docker-compose.yml up --build`（含 postgres→migrate→api/worker；env 见 `deploy/.env.example`）。

## 4. 后端验证门（每阶段收口必须全绿）
```bash
cd backend
uv run pytest -q                       # 全量（含集成；需 DB 在跑且已 migrate）→ 现 49 passed
uv run pytest -q -m "not integration"  # 离线档（无需 DB）→ 现 31 passed
uv run lint-imports                     # 架构依赖契约 → 4 kept / 0 broken
uv run ruff check . && uv run ruff format --check .
uv run mypy                             # strict，37 source files
```
> 集成测试无 DB 时会因连接被拒报错（无自动 skip）；无 DB 环境先只跑离线档。

## 5. 下一步：P0-4 前端控制台（7 任务）
- **计划（已跟踪）**：`docs/superpowers/plans/2026-06-27-p0-4-frontend-console.md`。
- 任务：①Vite+React+TS 脚手架工具链 ②orval 生成+axios 拆包层 ③登录 ④模型配置页（厂商/模型/测连通）⑤用量·trace 查看 ⑥路由+布局 ⑦Docker Compose `web` 服务。
- 栈：Vite·React18·TS strict·Ant Design5·TanStack Query5·React Router6·axios·orval·Vitest。
- **orval 取数（控制器决策）**：用**静态 openapi.json 快照**而非 `http://localhost:8000`，保证确定性、不依赖常驻后端：
  ```bash
  cd backend && uv run python -c "import json; from agent_hify.main import create_app; print(json.dumps(create_app().openapi(), ensure_ascii=False))" > ../frontend/openapi.json
  ```
  `orval.config.ts` 的 `input` 指向本地 `./openapi.json`；生成物入库**不手改**。
- **关键纪律**：统一响应恒 HTTP 200，axios 层拆 `data`、按 `code` 判错（`0`=成功，`11001/12001` 跳登录）；接口类型一律 orval 生成、禁手写/手改生成物。

## 6. 执行模式与评审纪律
- **批量实现 + 全分支总评审**：一个子代理按整份计划批量 TDD 实现（去每任务评审），计划末做一次 opus fresh-eyes 全分支总评审 + 控制器对风险点定点核验（实查证据，不照单全收）。详见 METHODOLOGY §2bis。
- **绿灯≠正确**：总评审主打未被测的边角/异常/序列化/并发路径与中央收口处。
- **Git**：用户已授权本项目 git 写；提交信息中文/Conventional、末尾带 `Co-Authored-By: Claude Opus 4.8`；**push 等外发前向用户确认**。
- **自主节奏**：默认按 yes 推进，仅在「submit（push/PR/发布）」或「多方案抉择」时中断给用户决策。

## 7. 延后 Minor 登记（来自各阶段总评审，尚未处理）
> 原仅存于 gitignored 的 SDD 账本，此处固化以免换环境丢失。无 Critical；50 人内网/单实例可接受。
- **P0-2**：M1 登录失败不做 bcrypt→时序枚举（低危）；M3 生产默认密钥缺 fail-fast 校验（留部署阶段）；M5 杂项（db nullable 冗余/decode_cursor 无 try/test 魔法数/logging 非幂等/命名遮蔽内建/CITEXT 写法）。
- **P0-3**：#7 熔断半开非单探测且 `allow()` 有副作用（单实例低危）；#8 observability usage/trace 列表缺分页·上限（留 P0-4 前端消费时按 standards 补）；#11 全局 Semaphore/CircuitBreaker 跨事件循环（仅多 event-loop 测试态隐患）；#12 "identity depends only on core" 契约禁 identity→observability 与"任意模块可向下调 observability"措辞微冲突；trace input/output 未脱敏；`Trace.status` 无 DB CheckConstraint；集成测试随机名不清理（DB rows 累积）；`uq_usage_daily_dim` 依赖 PG15+ NULLS NOT DISTINCT（切版本需确认）；litellm ~百传递依赖（已接受）。

## 8. 不随 git 走的本地状态（换环境会丢，知悉即可）
- `.superpowers/sdd/progress.md`（SDD 详细账本）—— **被 git 忽略**，仅原机本地。本文件 §1–§7 已提炼其关键内容。
- `~/.claude/.../memory/`（记忆）—— 本机本地。
- 原机工作树有**未跟踪的 `frontend/` 半成品**（P0-4 子代理仅完成 Task 1 脚手架，未提交、已停）—— 不会随仓库；新环境从 P0-4 计划全新开始即可。
