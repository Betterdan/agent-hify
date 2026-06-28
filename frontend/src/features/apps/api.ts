import { request } from '@/lib/api/http';

export interface AppOut {
  id: number;
  type: string;
  name: string;
  config: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AppConfigChat {
  model_id: number;
  system_prompt?: string;
  params?: Record<string, unknown>;
  history_limit?: number;
}

export function listApps(): Promise<AppOut[]> {
  return request({ url: '/api/v1/apps', method: 'get' });
}

export function createApp(body: { name: string; config: AppConfigChat }): Promise<AppOut> {
  return request({
    url: '/api/v1/apps',
    method: 'post',
    data: { type: 'chat', name: body.name, config: body.config },
  });
}

export function deleteApp(appId: number): Promise<null> {
  return request({ url: `/api/v1/apps/${appId}`, method: 'delete' });
}
