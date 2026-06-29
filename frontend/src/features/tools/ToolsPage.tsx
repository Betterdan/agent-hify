import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Badge,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  message,
} from 'antd';
import { useState } from 'react';

import { createTool, deleteTool, listTools, updateTool, type ToolOut } from '@/features/tools/api';
import { ApiError } from '@/lib/api/http';

const TOOL_TYPES = [
  { value: 'builtin', label: '内置工具' },
  { value: 'api', label: 'API 工具' },
  { value: 'mcp', label: 'MCP 工具' },
];

export function ToolsPage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: tools = [], isLoading } = useQuery({
    queryKey: ['tools'],
    queryFn: listTools,
  });

  const createMutation = useMutation({
    mutationFn: createTool,
    onSuccess: () => {
      message.success('已创建');
      setCreateOpen(false);
      form.resetFields();
      void qc.invalidateQueries({ queryKey: ['tools'] });
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : '创建失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTool,
    onSuccess: () => {
      message.success('已删除');
      void qc.invalidateQueries({ queryKey: ['tools'] });
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : '删除失败'),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ toolId, enabled }: { toolId: number; enabled: boolean }) =>
      updateTool(toolId, { enabled }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['tools'] }),
    onError: (e) => message.error(e instanceof ApiError ? e.message : '更新失败'),
  });

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Button type="primary" onClick={() => setCreateOpen(true)}>
        新建工具
      </Button>

      <Table
        loading={isLoading}
        dataSource={tools}
        rowKey="id"
        columns={[
          { title: '名称', dataIndex: 'name' },
          {
            title: '类型',
            dataIndex: 'type',
            render: (t: string) => {
              const colors: Record<string, string> = {
                builtin: 'green',
                api: 'blue',
                mcp: 'purple',
              };
              return <Badge color={colors[t] ?? 'default'} text={t} />;
            },
          },
          {
            title: '启用',
            dataIndex: 'enabled',
            render: (enabled: boolean, record: ToolOut) => (
              <Switch
                checked={enabled}
                onChange={(v) => toggleMutation.mutate({ toolId: record.id, enabled: v })}
              />
            ),
          },
          {
            title: '操作',
            render: (_: unknown, record: ToolOut) => (
              <Popconfirm
                title="确认删除该工具？"
                onConfirm={() => deleteMutation.mutate(record.id)}
              >
                <a>删除</a>
              </Popconfirm>
            ),
          },
        ]}
      />

      <Modal
        title="新建工具"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={(v) =>
            createMutation.mutate({
              ...v,
              schema: {},
              config: {},
              enabled: true,
            })
          }
        >
          <Form.Item name="type" label="工具类型" rules={[{ required: true }]}>
            <Select options={TOOL_TYPES} />
          </Form.Item>
          <Form.Item name="name" label="工具名称" rules={[{ required: true }]}>
            <Input placeholder="如：datetime, my-api-tool" />
          </Form.Item>
          <Form.Item name="credentials" label="凭证（可选）">
            <Input.Password placeholder="Bearer token / API key" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
