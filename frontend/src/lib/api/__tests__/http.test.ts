import MockAdapter from 'axios-mock-adapter';
import { beforeEach, expect, test } from 'vitest';

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
