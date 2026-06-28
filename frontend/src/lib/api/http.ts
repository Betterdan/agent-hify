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
