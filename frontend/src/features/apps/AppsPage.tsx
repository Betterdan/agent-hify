import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  Modal,
  Popconfirm,
  Row,
  Select,
  Slider,
  Space,
  message,
} from 'antd';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { createApp, deleteApp, listApps } from '@/features/apps/api';
import { listModels } from '@/features/models/api';
import { ApiError } from '@/lib/api/http';

export function AppsPage() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const { data: apps = [] } = useQuery({ queryKey: ['apps'], queryFn: listApps });
  const { data: models = [] } = useQuery({ queryKey: ['models'], queryFn: listModels });

  const create = useMutation({
    mutationFn: (v: {
      name: string;
      model_id: number;
      system_prompt?: string;
      temperature: number;
    }) =>
      createApp({
        name: v.name,
        config: {
          model_id: v.model_id,
          system_prompt: v.system_prompt ?? '',
          params: { temperature: v.temperature, max_tokens: 2048 },
        },
      }),
    onSuccess: () => {
      message.success('已创建');
      setOpen(false);
      form.resetFields();
      void qc.invalidateQueries({ queryKey: ['apps'] });
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : '创建失败'),
  });

  const remove = useMutation({
    mutationFn: deleteApp,
    onSuccess: () => {
      message.success('已删除');
      void qc.invalidateQueries({ queryKey: ['apps'] });
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : '删除失败'),
  });

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Button type="primary" onClick={() => setOpen(true)}>
        新建应用
      </Button>
      <Row gutter={[16, 16]}>
        {apps.map((app) => (
          <Col key={app.id} span={8}>
            <Card
              title={app.name}
              actions={[
                <Link key="chat" to={`/apps/${app.id}/chat`}>
                  进入对话
                </Link>,
                <Popconfirm
                  key="del"
                  title="确认删除该应用？"
                  onConfirm={() => remove.mutate(app.id)}
                >
                  <a>删除</a>
                </Popconfirm>,
              ]}
            >
              <div>类型：{app.type}</div>
              <div>状态：{app.status}</div>
            </Card>
          </Col>
        ))}
      </Row>

      <Modal
        title="新建应用"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={create.isPending}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ temperature: 0.7 }}
          onFinish={(v) => create.mutate(v)}
        >
          <Form.Item name="name" label="应用名" rules={[{ required: true }]}>
            <Input placeholder="如：客服助手" />
          </Form.Item>
          <Form.Item name="model_id" label="模型" rules={[{ required: true }]}>
            <Select
              placeholder="选择模型"
              options={models.map((m) => ({ value: m.id, label: m.model_key }))}
            />
          </Form.Item>
          <Form.Item name="system_prompt" label="系统提示">
            <Input.TextArea rows={3} placeholder="你是一个乐于助人的助手" />
          </Form.Item>
          <Form.Item name="temperature" label="Temperature">
            <Slider min={0} max={2} step={0.1} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
