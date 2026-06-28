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
