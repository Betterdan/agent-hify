# 功能记忆：认证与用户 (Auth)

## 当前状态

**整体**：✅ P0 完成

| 子功能 | 状态 | 备注 |
|---|---|---|
| JWT 登录 | ✅ | |
| 密码哈希 | ✅ | bcrypt |
| workspace_id 隔离 | ✅ | 所有查询携带 |
| 种子账号 | ✅ | admin@agent-hify.local / admin123 |
| 多用户注册 | ❌ | P0 不在范围，预留接口 |

## 关键文件

```
backend/src/agent_hify/modules/auth/
  router.py       # POST /api/v1/auth/login
  service.py
  schemas.py

backend/src/agent_hify/core/security.py  # encrypt/decrypt, hash_password
```

## 已知问题

- 无用户注册界面（目前只有种子账号）

## 设计决策

- 单工作区但始终携带 `workspace_id`（预埋多工作区，UI 不暴露切换）
- 凭证加密：`core.security.encrypt()`/`decrypt()`，不明文存 DB

## 接口摘要

```
POST /api/v1/auth/login     # 登录，返回 JWT access_token
GET  /api/v1/auth/me        # 当前用户信息
```

## 测试覆盖

- 后端：登录流程、JWT 验证、workspace 隔离
