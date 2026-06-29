import { useQuery } from '@tanstack/react-query';
import { Card, Space, Table, Tag, Typography } from 'antd';

import { listTraces, listUsage, type TraceOut } from '@/features/observability/api';

const { Text } = Typography;

export function ObservabilityPage() {
  const { data: traces = [] } = useQuery({
    queryKey: ['traces'],
    queryFn: () => listTraces({ days: 7, limit: 100 }),
  });
  const { data: usage = [] } = useQuery({ queryKey: ['usage'], queryFn: listUsage });

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="用量（按天）">
        <Table
          rowKey={(r) => `${r.day}-${r.model_id}`}
          dataSource={usage}
          pagination={false}
          columns={[
            { title: '日期', dataIndex: 'day' },
            { title: '模型', dataIndex: 'model_id' },
            { title: 'tokens_in', dataIndex: 'tokens_in' },
            { title: 'tokens_out', dataIndex: 'tokens_out' },
            { title: '成本', dataIndex: 'cost' },
            { title: '请求数', dataIndex: 'requests' },
          ]}
        />
      </Card>
      <Card title="Trace">
        <Table<TraceOut>
          rowKey="id"
          dataSource={traces}
          pagination={false}
          columns={[
            { title: '类型', dataIndex: 'type' },
            {
              title: '状态',
              dataIndex: 'status',
              render: (s: string) => (
                <Tag color={s === 'ok' ? 'green' : 'red'}>{s}</Tag>
              ),
            },
            { title: 'App', dataIndex: 'app_id', render: (v: number | null) => v ?? '-' },
            { title: 'tokens_in', dataIndex: 'tokens_in' },
            { title: 'tokens_out', dataIndex: 'tokens_out' },
            { title: '延迟(ms)', dataIndex: 'latency_ms' },
            {
              title: '错误',
              dataIndex: 'error',
              ellipsis: true,
              render: (e: string | null) => e ? <Text type="danger">{e}</Text> : '-',
            },
            { title: '时间', dataIndex: 'created_at' },
          ]}
        />
      </Card>
    </Space>
  );
}
