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
