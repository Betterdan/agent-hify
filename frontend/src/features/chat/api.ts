import { request } from '@/lib/api/http';
import { getToken } from '@/lib/auth/token';

export interface ConversationOut {
  id: number;
  app_id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageOut {
  id: number;
  conversation_id: number;
  role: string;
  content: { type: string; text?: string }[];
  created_at: string;
}

interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}

export function listConversations(appId: number): Promise<CursorPage<ConversationOut>> {
  return request({ url: `/api/v1/apps/${appId}/conversations`, method: 'get' });
}

export function listMessages(convId: number): Promise<CursorPage<MessageOut>> {
  return request({ url: `/api/v1/conversations/${convId}/messages`, method: 'get' });
}

export interface ChatStreamHandlers {
  onDelta: (text: string) => void;
  onUsage?: (u: { tokens_in: number; tokens_out: number; cost: string }) => void;
  onDone?: (d: { conversation_id: number; message_id: number }) => void;
  onError?: (e: { code: number; message: string }) => void;
}

export async function streamChat(
  appId: number,
  body: { conversation_id?: number; message: string },
  handlers: ChatStreamHandlers,
): Promise<void> {
  const token = getToken();
  const resp = await fetch(`/api/v1/apps/${appId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    handlers.onError?.({ code: resp.status, message: `请求失败 (${resp.status})` });
    return;
  }
  if (!resp.body) return;

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const dispatch = (block: string): void => {
    let event = 'message';
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) event = line.slice(7);
      else if (line.startsWith('data: ')) data = line.slice(6);
    }
    if (!data) return;
    const parsed = JSON.parse(data) as unknown as Record<string, unknown>;
    if (event === 'message') handlers.onDelta(parsed.delta as string);
    else if (event === 'usage')
      handlers.onUsage?.(parsed as unknown as { tokens_in: number; tokens_out: number; cost: string });
    else if (event === 'done')
      handlers.onDone?.(parsed as unknown as { conversation_id: number; message_id: number });
    else if (event === 'error')
      handlers.onError?.(parsed as unknown as { code: number; message: string });
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      if (block.trim()) dispatch(block);
    }
  }
}
