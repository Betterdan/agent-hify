import { useQuery } from '@tanstack/react-query';
import { Card, Space, Table } from 'antd';

import { listTraces, listUsage } from '@/features/observability/api';

export function ObservabilityPage() {
  const { data: traces = [] } = useQuery({ queryKey: ['traces'], queryFn: listTraces });
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
        <Table
          rowKey="id"
          dataSource={traces}
          pagination={false}
          columns={[
            { title: '类型', dataIndex: 'type' },
            { title: '状态', dataIndex: 'status' },
            { title: 'tokens_in', dataIndex: 'tokens_in' },
            { title: 'tokens_out', dataIndex: 'tokens_out' },
            { title: '延迟(ms)', dataIndex: 'latency_ms' },
            { title: '时间', dataIndex: 'created_at' },
          ]}
        />
      </Card>
    </Space>
  );
}
