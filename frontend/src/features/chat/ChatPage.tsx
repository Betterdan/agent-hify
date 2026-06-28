import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Input, Layout, List, Space } from 'antd';
import { useState } from 'react';
import { useParams } from 'react-router-dom';

import {
  listConversations,
  listMessages,
  streamChat,
  type MessageOut,
} from '@/features/chat/api';

interface Bubble {
  role: string;
  text: string;
}

function toBubbles(messages: MessageOut[]): Bubble[] {
  return messages.map((m) => ({
    role: m.role,
    text: m.content.map((c) => c.text ?? '').join(''),
  }));
}

export function ChatPage() {
  const { appId } = useParams<{ appId: string }>();
  const appIdNum = Number(appId);
  const qc = useQueryClient();

  const [activeConv, setActiveConv] = useState<number | null>(null);
  const [draft, setDraft] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [bubbles, setBubbles] = useState<Bubble[]>([]);

  const { data: convPage } = useQuery({
    queryKey: ['conversations', appIdNum],
    queryFn: () => listConversations(appIdNum),
  });

  const openConversation = async (convId: number): Promise<void> => {
    setActiveConv(convId);
    const page = await listMessages(convId);
    setBubbles(toBubbles(page.items));
  };

  const newConversation = (): void => {
    setActiveConv(null);
    setBubbles([]);
  };

  const send = async (): Promise<void> => {
    if (!draft.trim() || streaming) return;
    const text = draft;
    setDraft('');
    setBubbles((prev) => [...prev, { role: 'user', text }, { role: 'assistant', text: '' }]);
    setStreaming(true);

    await streamChat(
      appIdNum,
      { conversation_id: activeConv ?? undefined, message: text },
      {
        onDelta: (delta) =>
          setBubbles((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              role: 'assistant',
              text: next[next.length - 1].text + delta,
            };
            return next;
          }),
        onDone: (d) => {
          setActiveConv(d.conversation_id);
          void qc.invalidateQueries({ queryKey: ['conversations', appIdNum] });
        },
      },
    );
    setStreaming(false);
  };

  return (
    <Layout style={{ height: 'calc(100vh - 112px)' }}>
      <Layout.Sider width={240} theme="light" style={{ padding: 12, overflow: 'auto' }}>
        <Button block onClick={newConversation} style={{ marginBottom: 12 }}>
          新建对话
        </Button>
        <List
          dataSource={convPage?.items ?? []}
          renderItem={(conv) => (
            <List.Item
              onClick={() => void openConversation(conv.id)}
              style={{
                cursor: 'pointer',
                fontWeight: conv.id === activeConv ? 600 : 400,
              }}
            >
              {conv.title || `对话 #${conv.id}`}
            </List.Item>
          )}
        />
      </Layout.Sider>
      <Layout.Content style={{ display: 'flex', flexDirection: 'column', padding: 16 }}>
        <div style={{ flex: 1, overflow: 'auto' }}>
          {bubbles.map((b, i) => (
            <div
              key={i}
              style={{ textAlign: b.role === 'user' ? 'right' : 'left', margin: '8px 0' }}
            >
              <span
                style={{
                  display: 'inline-block',
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: b.role === 'user' ? '#1677ff' : '#f0f0f0',
                  color: b.role === 'user' ? '#fff' : '#000',
                  maxWidth: '70%',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {b.text}
              </span>
            </div>
          ))}
        </div>
        <Space.Compact style={{ width: '100%', marginTop: 12 }}>
          <Input
            value={draft}
            disabled={streaming}
            onChange={(e) => setDraft(e.target.value)}
            onPressEnter={() => void send()}
            placeholder="输入消息，回车发送"
          />
          <Button type="primary" disabled={streaming} onClick={() => void send()}>
            发送
          </Button>
        </Space.Compact>
      </Layout.Content>
    </Layout>
  );
}
