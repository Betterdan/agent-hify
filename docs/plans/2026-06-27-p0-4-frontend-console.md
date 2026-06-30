# P0-4 前端控制台（最小可用）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地最小前端控制台：登录、模型配置（厂商+模型、测连通）、用量/trace 查看；接口类型由后端 OpenAPI 经 orval 生成（不手写），统一响应在 axios 层拆包，纳入 Docker Compose 一键起。

**Architecture:** Vite + React + TypeScript 单页应用，feature-based 目录（DESIGN.md §8）。所有后端调用经一个 axios 实例：注入 Bearer，**响应永远 HTTP 200**，故在拦截器里按 `body.code` 判错（鉴权类码跳登录）。orval 从 `/openapi.json` 生成 TanStack Query hooks 与 TS 类型。

**Tech Stack:** Vite · React 18 · TypeScript(strict) · Ant Design 5 · TanStack Query 5 · React Router 6 · axios · orval · Vitest + React Testing Library · ESLint + Prettier

## Global Constraints

- Node `>=20`；包管理 `npm`；TS `strict: true`，路径别名 `@/` → `src/`。
- Lint/格式化 `ESLint(typescript-eslint)` + `Prettier`。
- **接口类型一律由 orval 生成到 `src/lib/api/generated/`，禁止手写、禁止手改生成物**（DESIGN.md §9）。
- 统一响应：后端恒 HTTP 200 + `{code,data,message}`；前端在 axios 层拆 `data`、按 `code` 判错（`0`=成功）。
- 鉴权：token 存 `localStorage`；请求注入 `Authorization: Bearer`；`code∈{11001,12001}` 跳登录。
- 空值：后端已保证列表 `[]`/字符串 `""`，前端不额外兜底 null。
- 组件测试以冒烟为主（渲染 + 关键交互），外部请求 mock。
- 提交信息用 Conventional Commits。
- 前端工作目录 `frontend/`；命令默认在该目录执行。

---

### Task 1: Vite + React + TS 脚手架与工具链

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/.eslintrc.cjs`
- Create: `frontend/.prettierrc`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/vite-env.d.ts`
- Create: `frontend/src/app/__tests__/App.test.tsx`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`

**Interfaces:**
- Produces: 可 `npm run dev` 启动、`npm run build` 构建、`npm run test` 跑 Vitest 的前端工程；`App` 根组件。

- [ ] **Step 1: 写 package.json**

`frontend/package.json`:
```json
{
  "name": "agent-hify-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint . --max-warnings 0",
    "format:check": "prettier --check .",
    "test": "vitest run",
    "gen:api": "orval --config orval.config.ts"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "antd": "^5.22.0",
    "@tanstack/react-query": "^5.62.0",
    "axios": "^1.7.9"
  },
  "devDependencies": {
    "typescript": "^5.7.2",
    "vite": "^6.0.3",
    "@vitejs/plugin-react": "^4.3.4",
    "@types/react": "^18.3.17",
    "@types/react-dom": "^18.3.5",
    "eslint": "^9.17.0",
    "typescript-eslint": "^8.18.1",
    "eslint-plugin-react-hooks": "^5.1.0",
    "prettier": "^3.4.2",
    "vitest": "^2.1.8",
    "jsdom": "^25.0.1",
    "@testing-library/react": "^16.1.0",
    "@testing-library/jest-dom": "^6.6.3",
    "orval": "^7.3.0"
  }
}
```

- [ ] **Step 2: 写 TS / Vite / Vitest 配置**

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src"]
}
```

`frontend/vite.config.ts`:
```ts
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
});
```

`frontend/vitest.config.ts`:
```ts
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
});
```

`frontend/src/test/setup.ts`:
```ts
import '@testing-library/jest-dom';
```

- [ ] **Step 3: 写 ESLint / Prettier / index.html / 入口**

`frontend/.eslintrc.cjs`:
```js
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  plugins: ['@typescript-eslint', 'react-hooks'],
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  ignorePatterns: ['dist', 'src/lib/api/generated'],
  rules: { 'react-hooks/rules-of-hooks': 'error' },
};
```

`frontend/.prettierrc`:
```json
{ "singleQuote": true, "semi": true, "printWidth": 100 }
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>agent-hify 控制台</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/src/vite-env.d.ts`:
```ts
/// <reference types="vite/client" />
```

`frontend/src/app/App.tsx`:
```tsx
export function App() {
  return <div>agent-hify</div>;
}
```

`frontend/src/main.tsx`:
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from '@/app/App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 4: 写冒烟测试**

`frontend/src/app/__tests__/App.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react';

import { App } from '@/app/App';

test('renders app name', () => {
  render(<App />);
  expect(screen.getByText('agent-hify')).toBeInTheDocument();
});
```

- [ ] **Step 5: 安装并验证**

Run:
```bash
cd frontend && npm install && npm run test && npm run build
```
Expected: 测试 1 passed；构建产出 `dist/`。

- [ ] **Step 6: 提交**

```bash
git add frontend/
git commit -m "feat(frontend): vite + react + ts scaffold with toolchain"
```

---

### Task 2: axios 实例 + 统一响应拆包 + orval 生成客户端

**Files:**
- Create: `frontend/src/lib/api/http.ts`（axios 实例 + 拦截器 + 拆包）
- Create: `frontend/src/lib/api/mutator.ts`（orval 用的请求函数）
- Create: `frontend/src/lib/auth/token.ts`（token 存取）
- Create: `frontend/orval.config.ts`
- Create: `frontend/src/lib/api/__tests__/http.test.ts`

**Interfaces:**
- Produces:
  - `lib/auth/token.ts`：`getToken()`、`setToken(t)`、`clearToken()`。
  - `lib/api/http.ts`：`http`（axios 实例）；响应拦截器把 `{code,data,message}` 拆成 `data`，`code!==0` 抛 `ApiError(code,message)`，鉴权类码清 token 并跳 `/login`。
  - `lib/api/mutator.ts`：`customRequest<T>(config) => Promise<T>`（orval 的 mutator）。
  - `orval.config.ts`：从 `http://localhost:8000/openapi.json` 生成到 `src/lib/api/generated/`，用 react-query + 上述 mutator。

- [ ] **Step 1: 写 token 与 http**

`frontend/src/lib/auth/token.ts`:
```ts
const KEY = 'agent_hify_token';

export function getToken(): string | null {
  return localStorage.getItem(KEY);
}
export function setToken(token: string): void {
  localStorage.setItem(KEY, token);
}
export function clearToken(): void {
  localStorage.removeItem(KEY);
}
```

`frontend/src/lib/api/http.ts`:
```ts
import axios, { type AxiosRequestConfig } from 'axios';

import { clearToken, getToken } from '@/lib/auth/token';

const AUTH_CODES = new Set([11001, 12001]);

export class ApiError extends Error {
  code: number;
  constructor(code: number, message: string) {
    super(message);
    this.code = code;
  }
}

export const http = axios.create({ baseURL: '/' });

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use((response) => {
  const body = response.data as { code: number; message: string; data: unknown };
  if (body.code !== 0) {
    if (AUTH_CODES.has(body.code)) {
      clearToken();
      if (window.location.pathname !== '/login') {
        window.location.assign('/login');
      }
    }
    throw new ApiError(body.code, body.message);
  }
  // 用 data 替换 response.data，使 orval 生成的 hook 直接拿到业务数据
  response.data = body.data;
  return response;
});

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const resp = await http.request<T>(config);
  return resp.data;
}
```

`frontend/src/lib/api/mutator.ts`:
```ts
import { type AxiosRequestConfig } from 'axios';

import { request } from '@/lib/api/http';

export function customRequest<T>(config: AxiosRequestConfig): Promise<T> {
  return request<T>(config);
}

export default customRequest;
```

- [ ] **Step 2: 写 http 单测（mock axios 适配器）**

`frontend/src/lib/api/__tests__/http.test.ts`:
```ts
import MockAdapter from 'axios-mock-adapter';
import { beforeEach, expect, test, vi } from 'vitest';

import { ApiError, http, request } from '@/lib/api/http';

// 需要安装：axios-mock-adapter（见下方说明加入 devDependencies）
const mock = new MockAdapter(http);

beforeEach(() => mock.reset());

test('unwraps data on code 0', async () => {
  mock.onGet('/x').reply(200, { code: 0, message: 'ok', data: { v: 1 } });
  const out = await request<{ v: number }>({ url: '/x', method: 'get' });
  expect(out.v).toBe(1);
});

test('throws ApiError on non-zero code', async () => {
  mock.onGet('/y').reply(200, { code: 33001, message: '模型不存在', data: null });
  await expect(request({ url: '/y', method: 'get' })).rejects.toBeInstanceOf(ApiError);
});
```
> 安装：在 `frontend/package.json` 的 `devDependencies` 加 `"axios-mock-adapter": "^2.1.0"`，然后 `cd frontend && npm install`。

- [ ] **Step 3: 写 orval 配置**

`frontend/orval.config.ts`:
```ts
import { defineConfig } from 'orval';

export default defineConfig({
  agentHify: {
    input: 'http://localhost:8000/openapi.json',
    output: {
      mode: 'tags-split',
      target: 'src/lib/api/generated',
      client: 'react-query',
      override: {
        mutator: { path: 'src/lib/api/mutator.ts', name: 'customRequest' },
      },
    },
  },
});
```

- [ ] **Step 4: 生成客户端（需后端在跑）**

前置：后端起在 8000（`cd deploy && docker compose up -d` 或本机 `uvicorn`）。
Run:
```bash
cd frontend && npm run gen:api
```
Expected: 生成 `src/lib/api/generated/`（按 tag 分文件，含 react-query hooks 与 TS 类型）。
> 生成物入库但**不手改**；后端接口变更后重跑 `npm run gen:api`。若 CI 无后端，可提交一份 `openapi.json` 快照并把 `input` 指向该文件。

- [ ] **Step 5: 验证类型与测试**

Run: `cd frontend && npm run test && npm run build`
Expected: http 测试通过；构建通过（含生成物类型检查）。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/lib frontend/orval.config.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): axios layer with envelope unwrap and orval-generated client"
```

---

### Task 3: 应用外壳（QueryClient / Router / antd / 布局 / 鉴权守卫）

**Files:**
- Create: `frontend/src/app/queryClient.ts`
- Create: `frontend/src/app/routes.tsx`
- Create: `frontend/src/app/Layout.tsx`
- Create: `frontend/src/features/auth/RequireAuth.tsx`
- Modify: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/__tests__/routes.test.tsx`

**Interfaces:**
- Consumes: `lib/auth/token`、生成的 hooks（Task 2）。
- Produces:
  - `App` 内含 `QueryClientProvider` + antd `ConfigProvider` + `RouterProvider`。
  - `RequireAuth`：无 token 重定向 `/login`。
  - 路由：`/login`、`/`(重定向 `/models`)、`/models`、`/observability`，受保护页套 `Layout`。

- [ ] **Step 1: 写 queryClient 与布局**

`frontend/src/app/queryClient.ts`:
```ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});
```

`frontend/src/app/Layout.tsx`:
```tsx
import { Layout as AntLayout, Menu } from 'antd';
import { Link, Outlet, useLocation } from 'react-router-dom';

const items = [
  { key: '/models', label: <Link to="/models">模型</Link> },
  { key: '/observability', label: <Link to="/observability">用量 / Trace</Link> },
];

export function Layout() {
  const { pathname } = useLocation();
  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <AntLayout.Header>
        <Menu theme="dark" mode="horizontal" selectedKeys={[pathname]} items={items} />
      </AntLayout.Header>
      <AntLayout.Content style={{ padding: 24 }}>
        <Outlet />
      </AntLayout.Content>
    </AntLayout>
  );
}
```

- [ ] **Step 2: 写鉴权守卫与路由**

`frontend/src/features/auth/RequireAuth.tsx`:
```tsx
import { Navigate, Outlet } from 'react-router-dom';

import { getToken } from '@/lib/auth/token';

export function RequireAuth() {
  return getToken() ? <Outlet /> : <Navigate to="/login" replace />;
}
```

`frontend/src/app/routes.tsx`:
```tsx
import { createBrowserRouter, Navigate } from 'react-router-dom';

import { Layout } from '@/app/Layout';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { LoginPage } from '@/features/auth/LoginPage';
import { ModelsPage } from '@/features/models/ModelsPage';
import { ObservabilityPage } from '@/features/observability/ObservabilityPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: '/', element: <Navigate to="/models" replace /> },
          { path: '/models', element: <ModelsPage /> },
          { path: '/observability', element: <ObservabilityPage /> },
        ],
      },
    ],
  },
]);
```

- [ ] **Step 3: 改 App 装配**

`frontend/src/app/App.tsx`:
```tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { RouterProvider } from 'react-router-dom';

import { queryClient } from '@/app/queryClient';
import { router } from '@/app/routes';

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN}>
        <RouterProvider router={router} />
      </ConfigProvider>
    </QueryClientProvider>
  );
}
```
> 注：此步引用 `LoginPage`/`ModelsPage`/`ObservabilityPage`（Task 4–6 创建）。为使本任务可独立编译测试，先在各自路径创建占位组件：
> `frontend/src/features/auth/LoginPage.tsx`、`frontend/src/features/models/ModelsPage.tsx`、`frontend/src/features/observability/ObservabilityPage.tsx`，内容均为：
> ```tsx
> export function LoginPage() { return <div>login</div>; }
> ```
> （对应改名）。Task 4–6 再用完整实现覆盖。

- [ ] **Step 4: 写路由冒烟测试**

`frontend/src/app/__tests__/routes.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react';
import { beforeEach, expect, test } from 'vitest';

import { App } from '@/app/App';
import { clearToken } from '@/lib/auth/token';

beforeEach(() => clearToken());

test('redirects to login when unauthenticated', async () => {
  window.history.pushState({}, '', '/models');
  render(<App />);
  expect(await screen.findByText('login')).toBeInTheDocument();
});
```

- [ ] **Step 5: 验证**

Run: `cd frontend && npm run test && npm run build`
Expected: 路由测试通过；构建通过。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/app frontend/src/features
git commit -m "feat(frontend): app shell with router, query client, antd, auth guard"
```

---

### Task 4: 登录页

**Files:**
- Modify: `frontend/src/features/auth/LoginPage.tsx`
- Create: `frontend/src/features/auth/__tests__/LoginPage.test.tsx`

**Interfaces:**
- Consumes: 生成的登录 hook（orval 由 `POST /api/v1/auth/login` 生成，名称形如 `useLoginApiV1AuthLoginPost`）、`lib/auth/token.setToken`。
- Produces: 表单提交成功后存 token 并跳 `/models`。

> 说明：orval 生成的 hook 名依后端 `operationId` 而定。为不耦合具体生成名，本页**直接用 `request` 调接口**（仍走统一 axios 层），保持类型来自生成的类型文件。若已知生成 hook 名，可替换为该 hook。

- [ ] **Step 1: 写失败测试**

`frontend/src/features/auth/__tests__/LoginPage.test.tsx`:
```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MockAdapter from 'axios-mock-adapter';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, test, vi } from 'vitest';

import { LoginPage } from '@/features/auth/LoginPage';
import { http } from '@/lib/api/http';
import { getToken } from '@/lib/auth/token';

const mock = new MockAdapter(http);
beforeEach(() => mock.reset());

test('logs in and stores token', async () => {
  mock.onPost('/api/v1/auth/login').reply(200, {
    code: 0, message: 'ok', data: { access_token: 'tok-123', token_type: 'bearer' },
  });
  render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );
  await userEvent.type(screen.getByLabelText('邮箱'), 'admin@agent-hify.local');
  await userEvent.type(screen.getByLabelText('密码'), 'admin123');
  await userEvent.click(screen.getByRole('button', { name: '登录' }));
  await waitFor(() => expect(getToken()).toBe('tok-123'));
});
```
> 需要 `@testing-library/user-event`：加入 devDependencies `"@testing-library/user-event": "^14.5.2"` 并 `npm install`。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test -- LoginPage`
Expected: FAIL（占位组件无表单）

- [ ] **Step 3: 写登录页**

`frontend/src/features/auth/LoginPage.tsx`:
```tsx
import { Button, Card, Form, Input, message } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { request } from '@/lib/api/http';
import { ApiError } from '@/lib/api/http';
import { setToken } from '@/lib/auth/token';

interface LoginValues {
  email: string;
  password: string;
}
interface TokenData {
  access_token: string;
  token_type: string;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  async function onFinish(values: LoginValues) {
    setLoading(true);
    try {
      const data = await request<TokenData>({
        url: '/api/v1/auth/login',
        method: 'post',
        data: values,
      });
      setToken(data.access_token);
      navigate('/models', { replace: true });
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : '登录失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
      <Card title="agent-hify 登录" style={{ width: 360 }}>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item label="邮箱" name="email" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm run test -- LoginPage && npm run lint`
Expected: PASSED；lint 绿。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/features/auth frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): login page"
```

---

### Task 5: 模型配置页（厂商 + 模型 + 测连通）

**Files:**
- Modify: `frontend/src/features/models/ModelsPage.tsx`
- Create: `frontend/src/features/models/api.ts`（封装 request 调用，类型取自生成物）
- Create: `frontend/src/features/models/__tests__/ModelsPage.test.tsx`

**Interfaces:**
- Consumes: `request`、生成的类型（`ModelOut`/`ProviderOut` 等，从 `src/lib/api/generated`）。
- Produces: 模型列表表格；新建厂商+模型表单；每行"测连通"按钮（调 `POST /models/{id}/test-connectivity`，弹成功/失败）。

- [ ] **Step 1: 写 feature api 封装**

`frontend/src/features/models/api.ts`:
```ts
import { request } from '@/lib/api/http';

export interface ProviderOut {
  id: number;
  type: string;
  name: string;
  base_url: string | null;
  enabled: boolean;
}
export interface ModelOut {
  id: number;
  provider_id: number;
  model_key: string;
  type: string;
  capabilities: string[];
  embedding_dim: number | null;
  enabled: boolean;
}
export interface ConnectivityResult {
  ok: boolean;
  error: string | null;
}

export function listModels(): Promise<ModelOut[]> {
  return request({ url: '/api/v1/models', method: 'get' });
}
export function createProvider(body: {
  type: string;
  name: string;
  base_url?: string | null;
  credentials: Record<string, string>;
}): Promise<ProviderOut> {
  return request({ url: '/api/v1/model-providers', method: 'post', data: body });
}
export function createModel(body: {
  provider_id: number;
  model_key: string;
  type: string;
}): Promise<ModelOut> {
  return request({ url: '/api/v1/models', method: 'post', data: body });
}
export function testConnectivity(modelId: number): Promise<ConnectivityResult> {
  return request({ url: `/api/v1/models/${modelId}/test-connectivity`, method: 'post' });
}
```
> 说明：类型与后端 `ModelOut`/`ProviderOut` 字段对应；待 orval 生成稳定后，可改为直接引用 `src/lib/api/generated` 的类型，去掉此处手写接口体。

- [ ] **Step 2: 写失败测试**

`frontend/src/features/models/__tests__/ModelsPage.test.tsx`:
```tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import MockAdapter from 'axios-mock-adapter';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { ModelsPage } from '@/features/models/ModelsPage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

test('renders model list from api', async () => {
  mock.onGet('/api/v1/models').reply(200, {
    code: 0, message: 'ok',
    data: [{ id: 1, provider_id: 1, model_key: 'gpt-4o-mini', type: 'llm',
             capabilities: [], embedding_dim: null, enabled: true }],
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ModelsPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText('gpt-4o-mini')).toBeInTheDocument();
});
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd frontend && npm run test -- ModelsPage`
Expected: FAIL（占位组件）

- [ ] **Step 4: 写模型页**

`frontend/src/features/models/ModelsPage.tsx`:
```tsx
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Form, Input, message, Space, Table } from 'antd';

import {
  createModel,
  createProvider,
  listModels,
  type ModelOut,
  testConnectivity,
} from '@/features/models/api';

export function ModelsPage() {
  const qc = useQueryClient();
  const { data: models = [] } = useQuery({ queryKey: ['models'], queryFn: listModels });

  const connect = useMutation({
    mutationFn: testConnectivity,
    onSuccess: (r) => (r.ok ? message.success('连通正常') : message.error(r.error ?? '失败')),
  });

  const create = useMutation({
    mutationFn: async (v: {
      type: string;
      name: string;
      api_key: string;
      model_key: string;
    }) => {
      const prov = await createProvider({
        type: v.type,
        name: v.name,
        credentials: { api_key: v.api_key },
      });
      return createModel({ provider_id: prov.id, model_key: v.model_key, type: 'llm' });
    },
    onSuccess: () => {
      message.success('已创建');
      void qc.invalidateQueries({ queryKey: ['models'] });
    },
  });

  const columns = [
    { title: '模型', dataIndex: 'model_key' },
    { title: '类型', dataIndex: 'type' },
    {
      title: '操作',
      render: (_: unknown, row: ModelOut) => (
        <Button size="small" loading={connect.isPending} onClick={() => connect.mutate(row.id)}>
          测连通
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="新建模型">
        <Form layout="inline" onFinish={(v) => create.mutate(v)}>
          <Form.Item name="type" initialValue="openai" rules={[{ required: true }]}>
            <Input placeholder="厂商类型 openai" />
          </Form.Item>
          <Form.Item name="name" rules={[{ required: true }]}>
            <Input placeholder="厂商名" />
          </Form.Item>
          <Form.Item name="api_key" rules={[{ required: true }]}>
            <Input.Password placeholder="API Key" />
          </Form.Item>
          <Form.Item name="model_key" rules={[{ required: true }]}>
            <Input placeholder="模型 key 如 gpt-4o-mini" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={create.isPending}>
            创建
          </Button>
        </Form>
      </Card>
      <Card title="模型列表">
        <Table rowKey="id" dataSource={models} columns={columns} pagination={false} />
      </Card>
    </Space>
  );
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd frontend && npm run test -- ModelsPage && npm run lint`
Expected: PASSED；lint 绿。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/features/models
git commit -m "feat(frontend): models config page with create and connectivity test"
```

---

### Task 6: 用量 / Trace 查看页

**Files:**
- Modify: `frontend/src/features/observability/ObservabilityPage.tsx`
- Create: `frontend/src/features/observability/api.ts`
- Create: `frontend/src/features/observability/__tests__/ObservabilityPage.test.tsx`

**Interfaces:**
- Consumes: `request`。
- Produces: 两张表——traces（类型/状态/tokens/延迟/时间）与 usage（日期/模型/tokens/成本/请求数）。

- [ ] **Step 1: 写 feature api**

`frontend/src/features/observability/api.ts`:
```ts
import { request } from '@/lib/api/http';

export interface TraceOut {
  id: number;
  type: string;
  status: string;
  tokens_in: number;
  tokens_out: number;
  cost: string;
  latency_ms: number;
  created_at: string;
}
export interface UsageDailyOut {
  day: string;
  app_id: number | null;
  model_id: number | null;
  tokens_in: number;
  tokens_out: number;
  cost: string;
  requests: number;
}

export function listTraces(): Promise<TraceOut[]> {
  return request({ url: '/api/v1/observability/traces', method: 'get' });
}
export function listUsage(): Promise<UsageDailyOut[]> {
  return request({ url: '/api/v1/observability/usage', method: 'get' });
}
```

- [ ] **Step 2: 写失败测试**

`frontend/src/features/observability/__tests__/ObservabilityPage.test.tsx`:
```tsx
import { QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import MockAdapter from 'axios-mock-adapter';
import { beforeEach, expect, test } from 'vitest';

import { queryClient } from '@/app/queryClient';
import { ObservabilityPage } from '@/features/observability/ObservabilityPage';
import { http } from '@/lib/api/http';

const mock = new MockAdapter(http);
beforeEach(() => {
  mock.reset();
  queryClient.clear();
});

test('shows a trace row', async () => {
  mock.onGet('/api/v1/observability/traces').reply(200, {
    code: 0, message: 'ok',
    data: [{ id: 1, type: 'llm_call', status: 'ok', tokens_in: 8, tokens_out: 3,
             cost: '0.000900', latency_ms: 120, created_at: '2026-06-27T10:00:00Z' }],
  });
  mock.onGet('/api/v1/observability/usage').reply(200, { code: 0, message: 'ok', data: [] });
  render(
    <QueryClientProvider client={queryClient}>
      <ObservabilityPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText('llm_call')).toBeInTheDocument();
});
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd frontend && npm run test -- ObservabilityPage`
Expected: FAIL（占位组件）

- [ ] **Step 4: 写页面**

`frontend/src/features/observability/ObservabilityPage.tsx`:
```tsx
import { useQuery } from '@tanstack/react-query';
import { Card, Space, Table } from 'antd';

import { listTraces, listUsage } from '@/features/observability/api';

export function ObservabilityPage() {
  const { data: traces = [] } = useQuery({ queryKey: ['traces'], queryFn: listTraces });
  const { data: usage = [] } = useQuery({ queryKey: ['usage'], queryFn: listUsage });

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="用量（按天）">
        <Table
          rowKey={(r) => `${r.day}-${r.model_id}`}
          dataSource={usage}
          pagination={false}
          columns={[
            { title: '日期', dataIndex: 'day' },
            { title: '模型', dataIndex: 'model_id' },
            { title: 'tokens_in', dataIndex: 'tokens_in' },
            { title: 'tokens_out', dataIndex: 'tokens_out' },
            { title: '成本', dataIndex: 'cost' },
            { title: '请求数', dataIndex: 'requests' },
          ]}
        />
      </Card>
      <Card title="Trace">
        <Table
          rowKey="id"
          dataSource={traces}
          pagination={false}
          columns={[
            { title: '类型', dataIndex: 'type' },
            { title: '状态', dataIndex: 'status' },
            { title: 'tokens_in', dataIndex: 'tokens_in' },
            { title: 'tokens_out', dataIndex: 'tokens_out' },
            { title: '延迟(ms)', dataIndex: 'latency_ms' },
            { title: '时间', dataIndex: 'created_at' },
          ]}
        />
      </Card>
    </Space>
  );
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd frontend && npm run test && npm run lint && npm run build`
Expected: 全部测试 PASSED；lint 绿；构建通过。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/features/observability
git commit -m "feat(frontend): usage and trace viewer page"
```

---

### Task 7: 前端容器化 + 接入 Compose（一键起）

**Files:**
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`
- Create: `frontend/.dockerignore`
- Modify: `deploy/docker-compose.yml`（加 `web` 服务）

**Interfaces:**
- Produces: Compose 服务 `web`（80），nginx 托管前端构建并把 `/api` 反代到 `api:8000`；`docker compose up` 一键起全栈。

- [ ] **Step 1: 写 Dockerfile 与 nginx**

`frontend/Dockerfile`:
```dockerfile
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
```

`frontend/nginx.conf`:
```nginx
server {
  listen 80;
  location /api/ {
    proxy_pass http://api:8000;
    proxy_set_header Host $host;
  }
  location / {
    root /usr/share/nginx/html;
    try_files $uri /index.html;
  }
}
```

`frontend/.dockerignore`:
```
node_modules
dist
```

- [ ] **Step 2: 加 web 服务到 Compose**

在 `deploy/docker-compose.yml` 的 `services:` 下追加：
```yaml
  web:
    build: ../frontend
    ports: ["80:80"]
    depends_on:
      api: { condition: service_started }
```

- [ ] **Step 3: 验证一键起**

Run:
```bash
cd deploy && docker compose up -d --build
# 等 api 迁移：
cd ../backend && DATABASE_URL=postgresql+psycopg://hify:hify@localhost:5432/hify uv run alembic upgrade head
```
浏览器开 `http://localhost`，用 `admin@agent-hify.local` / `admin123` 登录 → 配置模型 → 测连通 → 看用量/trace。
> 真连模型需在模型页填真实可用的 API Key；仅验证 UI 流可先不连真模型。

- [ ] **Step 4: 关停并提交**

```bash
cd deploy && docker compose down
git add frontend/Dockerfile frontend/nginx.conf frontend/.dockerignore deploy/docker-compose.yml
git commit -m "chore(frontend): dockerize and add web service to compose"
```

---

## Self-Review

- **Spec coverage（对照 DESIGN §14 P0 第 1 项前端 + 第 7 项 + §8 前端组织）**：
  - 工程骨架前端（Vite/ts/antd/orval，T1/T2）✓ · feature-based 目录（T1 起）✓ · orval 生成、不手写接口类型（T2）✓。
  - 前端最小：登录（T4）✓ · 模型配置页（T5）✓ · 用量/trace 查看页（T6）✓。
  - Compose 一键起含前端（T7）✓。
- **Placeholder scan**：Task 3 引入的占位组件在 Task 4–6 被完整实现覆盖，非遗留空白；`features/*/api.ts` 手写接口体为过渡（已注明可切换到 orval 生成类型）。无 TBD。
- **Type consistency**：`request`/`ApiError`、`getToken/setToken/clearToken`、`queryClient`、`router`、`RequireAuth`、各 `features/*/api.ts` 的 `ModelOut/ProviderOut/ConnectivityResult/TraceOut/UsageDailyOut` 与后端 schema 字段一致；页面组件名 `LoginPage/ModelsPage/ObservabilityPage` 在路由与文件一致。
- **完成判据（本计划）**：`http://localhost` 能登录→配模型→测连通→看用量/trace；`npm run test`、`npm run lint`、`npm run build` 全绿；`docker compose up` 一键起 web+api+pg+redis(+worker)。

## 待执行者注意（已知风险点）

1. **统一响应 HTTP 200**：错误判定全靠 `body.code`，不是 HTTP 状态——`http.ts` 拦截器是唯一判错处，勿在页面再按 HTTP 状态判错。
2. **orval 依赖后端在跑**：`npm run gen:api` 需要 `/openapi.json` 可达；CI 无后端时改用提交的 openapi 快照（Task 2 Step 4 注）。本计划页面用 `features/*/api.ts` 手写 `request` 调用，**不阻塞于生成 hook 名**，生成物主要用于类型与未来替换。
3. **antd 版本与 React 18**：固定 antd 5.x；如升级注意 `ConfigProvider`/`message` API。
4. **依赖增补**：`axios-mock-adapter`、`@testing-library/user-event` 在对应任务加入 devDependencies；执行时确保 `npm install` 后再跑测试。
5. **真连模型**：测连通/调用走真实厂商需有效 Key 与出网；UI 验证可先不连真模型（仅验证表单与列表渲染）。
