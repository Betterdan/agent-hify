import { request } from '@/lib/api/http';

export interface TraceOut {
  id: number;
  type: string;
  status: string;
  app_id: number | null;
  conversation_id: number | null;
  message_id: number | null;
  tokens_in: number;
  tokens_out: number;
  cost: string;
  latency_ms: number;
  error: string | null;
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

export interface AnnotationOut {
  id: number;
  message_id: number;
  rating: number;
  comment: string | null;
  created_at: string;
}

export function listTraces(params?: {
  app_id?: number;
  status?: string;
  days?: number;
  limit?: number;
}): Promise<TraceOut[]> {
  const q = new URLSearchParams();
  if (params?.app_id != null) q.set('app_id', String(params.app_id));
  if (params?.status) q.set('status', params.status);
  if (params?.days != null) q.set('days', String(params.days));
  if (params?.limit != null) q.set('limit', String(params.limit));
  const qs = q.toString();
  return request({ url: `/api/v1/observability/traces${qs ? `?${qs}` : ''}`, method: 'get' });
}

export function listUsage(): Promise<UsageDailyOut[]> {
  return request({ url: '/api/v1/observability/usage', method: 'get' });
}

export function createAnnotation(body: {
  message_id: number;
  rating: number;
  comment?: string;
}): Promise<AnnotationOut> {
  return request({ url: '/api/v1/observability/annotations', method: 'post', data: body });
}
