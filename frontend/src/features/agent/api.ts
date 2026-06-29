import { getToken } from '@/lib/auth/token';

export interface StepEvent {
  iteration: number;
  tool_name: string;
  tool_args: Record<string, unknown>;
  tool_result: string;
  is_error: boolean;
}

export interface AgentHandlers {
  onStep?: (step: StepEvent) => void;
  onDelta?: (delta: string) => void;
  onUsage?: (usage: { tokens_in: number; tokens_out: number; cost: number }) => void;
  onDone?: (data: { conversation_id: number; message_id: number }) => void;
  onError?: (message: string) => void;
}

export async function runAgent(
  appId: number,
  body: { message: string; conversation_id?: number },
  handlers: AgentHandlers,
): Promise<void> {
  const token = getToken();
  const resp = await fetch(`/api/v1/apps/${appId}/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    handlers.onError?.(`请求失败：${resp.status}`);
    return;
  }

  const reader = resp.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() ?? '';
    for (const block of blocks) {
      const eventMatch = block.match(/^event: (\w+)/m);
      const dataMatch = block.match(/^data: (.+)/m);
      if (!eventMatch || !dataMatch) continue;
      const eventType = eventMatch[1];
      try {
        const payload = JSON.parse(dataMatch[1]) as Record<string, unknown>;
        if (eventType === 'step') handlers.onStep?.(payload as unknown as StepEvent);
        else if (eventType === 'message') handlers.onDelta?.(payload.delta as string);
        else if (eventType === 'usage')
          handlers.onUsage?.(
            payload as unknown as { tokens_in: number; tokens_out: number; cost: number },
          );
        else if (eventType === 'done')
          handlers.onDone?.(
            payload as unknown as { conversation_id: number; message_id: number },
          );
        else if (eventType === 'error') handlers.onError?.(payload.message as string);
      } catch {
        // ignore parse errors
      }
    }
  }
}
