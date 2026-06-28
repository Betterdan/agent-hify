import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Form, Input, message, Space, Table } from 'antd';

import {
  createModel,
  createProvider,
  listModels,
  type ModelOut,
  testConnectivity,
} from '@/features/models/api';
import { ApiError } from '@/lib/api/http';

export function ModelsPage() {
  const qc = useQueryClient();
  const { data: models = [] } = useQuery({ queryKey: ['models'], queryFn: listModels });

  const connect = useMutation({
    mutationFn: testConnectivity,
    onSuccess: (r) => (r.ok ? message.success('连通正常') : message.error(r.error ?? '失败')),
    onError: (e) => message.error(e instanceof ApiError ? e.message : '连通测试失败'),
  });

  const create = useMutation({
    mutationFn: async (v: {
      type: string;
      name: string;
      api_key: string;
      model_key: string;
    }) => {
      const prov = await createProvider({
        type: v.type,
        name: v.name,
        credentials: { api_key: v.api_key },
      });
      return createModel({ provider_id: prov.id, model_key: v.model_key, type: 'llm' });
    },
    onSuccess: () => {
      message.success('已创建');
      void qc.invalidateQueries({ queryKey: ['models'] });
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : '创建失败'),
  });

  const columns = [
    { title: '模型', dataIndex: 'model_key' },
    { title: '类型', dataIndex: 'type' },
    {
      title: '操作',
      render: (_: unknown, row: ModelOut) => (
        <Button size="small" loading={connect.isPending} onClick={() => connect.mutate(row.id)}>
          测连通
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="新建模型">
        <Form layout="inline" onFinish={(v) => create.mutate(v)}>
          <Form.Item name="type" initialValue="openai" rules={[{ required: true }]}>
            <Input placeholder="厂商类型 openai" />
          </Form.Item>
          <Form.Item name="name" rules={[{ required: true }]}>
            <Input placeholder="厂商名" />
          </Form.Item>
          <Form.Item name="api_key" rules={[{ required: true }]}>
            <Input.Password placeholder="API Key" />
          </Form.Item>
          <Form.Item name="model_key" rules={[{ required: true }]}>
            <Input placeholder="模型 key 如 gpt-4o-mini" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={create.isPending}>
            创建
          </Button>
        </Form>
      </Card>
      <Card title="模型列表">
        <Table rowKey="id" dataSource={models} columns={columns} pagination={false} />
      </Card>
    </Space>
  );
}
