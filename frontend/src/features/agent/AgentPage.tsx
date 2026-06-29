import { SendOutlined } from '@ant-design/icons';
import { Badge, Button, Card, Input, Layout, Space, Tag, Typography, message } from 'antd';
import { useRef, useState } from 'react';
import { useParams } from 'react-router-dom';

import { runAgent, type StepEvent } from '@/features/agent/api';

const { Content } = Layout;
const { Text } = Typography;

type MsgItem =
  | { kind: 'user'; text: string }
  | { kind: 'step'; step: StepEvent }
  | { kind: 'assistant'; text: string };

export function AgentPage() {
  const { appId } = useParams<{ appId: string }>();
  const [msgs, setMsgs] = useState<MsgItem[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [convId, setConvId] = useState<number | undefined>();
  const bottomRef = useRef<HTMLDivElement>(null);

  const append = (item: MsgItem) => setMsgs((prev) => [...prev, item]);

  const send = async () => {
    if (!input.trim() || streaming || !appId) return;
    const text = input.trim();
    setInput('');
    setStreaming(true);
    append({ kind: 'user', text });
    let assistantText = '';
    let assistantAdded = false;

    try {
      await runAgent(Number(appId), { message: text, conversation_id: convId }, {
        onStep: (step) => append({ kind: 'step', step }),
        onDelta: (delta) => {
          assistantText += delta;
          if (!assistantAdded) {
            assistantAdded = true;
            append({ kind: 'assistant', text: assistantText });
          } else {
            setMsgs((prev) => {
              const copy = [...prev];
              const lastIdx = copy.length - 1;
              if (copy[lastIdx]?.kind === 'assistant') {
                copy[lastIdx] = { kind: 'assistant', text: assistantText };
              }
              return copy;
            });
          }
        },
        onDone: (d) => setConvId(d.conversation_id),
        onError: (msg) => message.error(msg || '请求失败，请重试'),
      });
    } finally {
      setStreaming(false);
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <Content style={{ padding: 24, display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, overflowY: 'auto', marginBottom: 16 }}>
        {msgs.map((m, i) => {
          if (m.kind === 'user') {
            return (
              <div key={i} style={{ textAlign: 'right', marginBottom: 12 }}>
                <Tag color="blue">{m.text}</Tag>
              </div>
            );
          }
          if (m.kind === 'step') {
            return (
              <div key={i} style={{ marginBottom: 8 }}>
                <Card size="small" style={{ background: '#f6ffed', borderColor: '#b7eb8f' }}>
                  <Space>
                    <Badge color={m.step.is_error ? 'red' : 'green'} />
                    <Text type="secondary">
                      [{m.step.iteration}] {m.step.tool_name}
                    </Text>
                    <Text code style={{ fontSize: 11 }}>
                      {m.step.tool_result.slice(0, 80)}
                    </Text>
                  </Space>
                </Card>
              </div>
            );
          }
          return (
            <div key={i} style={{ marginBottom: 12 }}>
              <Tag>{m.text}</Tag>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>

      <Space.Compact style={{ width: '100%' }}>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={() => void send()}
          disabled={streaming}
          placeholder="输入消息，按 Enter 发送…"
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={streaming}
          onClick={() => void send()}
        />
      </Space.Compact>
    </Content>
  );
}
