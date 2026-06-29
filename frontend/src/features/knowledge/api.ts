import { request } from '@/lib/api/http';

export interface KbConfig {
  chunk_size?: number;
  overlap?: number;
  top_k?: number;
  threshold?: number | null;
}

export interface KnowledgeBaseOut {
  id: number;
  workspace_id: number;
  name: string;
  embedding_model_id: number;
  config: KbConfig;
  created_at: string;
  updated_at: string;
}

export interface DocumentOut {
  id: number;
  kb_id: number;
  filename: string;
  status: string;
  error: string | null;
  char_count: number;
  created_at: string;
  updated_at: string;
}

interface OffsetPage<T> {
  items: T[];
  total: number | null;
  page: number;
  page_size: number;
}

export function listKbs(page = 1): Promise<OffsetPage<KnowledgeBaseOut>> {
  return request({
    url: '/api/v1/knowledge_bases',
    method: 'get',
    params: { page, page_size: 20 },
  });
}

export function createKb(body: {
  name: string;
  embedding_model_id: number;
}): Promise<KnowledgeBaseOut> {
  return request({ url: '/api/v1/knowledge_bases', method: 'post', data: body });
}

export function deleteKb(kbId: number): Promise<null> {
  return request({ url: `/api/v1/knowledge_bases/${kbId}`, method: 'delete' });
}

export function listDocuments(kbId: number): Promise<OffsetPage<DocumentOut>> {
  return request({ url: `/api/v1/knowledge_bases/${kbId}/documents`, method: 'get' });
}

export async function uploadDocument(kbId: number, file: File): Promise<DocumentOut> {
  const formData = new FormData();
  formData.append('file', file);
  return request({
    url: `/api/v1/knowledge_bases/${kbId}/documents`,
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}
