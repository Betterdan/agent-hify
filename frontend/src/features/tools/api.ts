import { request } from '@/lib/api/http';

export interface ToolOut {
  id: number;
  workspace_id: number;
  type: string;
  name: string;
  schema: Record<string, unknown>;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ToolCreate {
  type: string;
  name: string;
  schema: Record<string, unknown>;
  credentials?: string;
  config: Record<string, unknown>;
  enabled: boolean;
}

export function listTools(): Promise<ToolOut[]> {
  return request({ url: '/api/v1/tools', method: 'get' });
}

export function createTool(body: ToolCreate): Promise<ToolOut> {
  return request({ url: '/api/v1/tools', method: 'post', data: body });
}

export function deleteTool(toolId: number): Promise<null> {
  return request({ url: `/api/v1/tools/${toolId}`, method: 'delete' });
}

export function updateTool(toolId: number, body: Partial<ToolCreate>): Promise<ToolOut> {
  return request({ url: `/api/v1/tools/${toolId}`, method: 'patch', data: body });
}
