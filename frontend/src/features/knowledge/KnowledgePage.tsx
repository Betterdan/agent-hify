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
  Space,
  Table,
  Tag,
  Upload,
  message,
} from 'antd';
import { useState } from 'react';

import {
  createKb,
  deleteKb,
  listDocuments,
  listKbs,
  uploadDocument,
  type KnowledgeBaseOut,
} from '@/features/knowledge/api';
import { listModels } from '@/features/models/api';
import { ApiError } from '@/lib/api/http';

const STATUS_COLOR: Record<string, string> = {
  pending: 'default',
  processing: 'processing',
  done: 'success',
  failed: 'error',
};

export function KnowledgePage() {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedKb, setSelectedKb] = useState<KnowledgeBaseOut | null>(null);
  const [form] = Form.useForm();

  const { data: kbPage } = useQuery({ queryKey: ['kbs'], queryFn: () => listKbs() });
  const { data: models = [] } = useQuery({ queryKey: ['models'], queryFn: listModels });
  const { data: docPage } = useQuery({
    queryKey: ['documents', selectedKb?.id],
    queryFn: () => (selectedKb ? listDocuments(selectedKb.id) : Promise.resolve(null)),
    enabled: !!selectedKb,
  });

  const embeddingModels = models.filter((m) => m.type === 'embedding');

  const createMutation = useMutation({
    mutationFn: (v: { name: string; embedding_model_id: number }) => createKb(v),
    onSuccess: () => {
      message.success('已创建');
      setCreateOpen(false);
      form.resetFields();
      void qc.invalidateQueries({ queryKey: ['kbs'] });
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : '创建失败'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteKb,
    onSuccess: () => {
      message.success('已删除');
      setSelectedKb(null);
      void qc.invalidateQueries({ queryKey: ['kbs'] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: ({ kbId, file }: { kbId: number; file: File }) => uploadDocument(kbId, file),
    onSuccess: () => {
      message.success('已上传，后台摄取中');
      void qc.invalidateQueries({ queryKey: ['documents', selectedKb?.id] });
    },
    onError: (e) => message.error(e instanceof ApiError ? e.message : '上传失败'),
  });

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Button type="primary" onClick={() => setCreateOpen(true)}>
        新建知识库
      </Button>

      <Row gutter={[16, 16]}>
        {(kbPage?.items ?? []).map((kb) => (
          <Col key={kb.id} span={8}>
            <Card
              title={kb.name}
              style={{
                cursor: 'pointer',
                border: selectedKb?.id === kb.id ? '2px solid #1677ff' : undefined,
              }}
              onClick={() => setSelectedKb(kb)}
              actions={[
                <Popconfirm
                  key="del"
                  title="确认删除该知识库？"
                  onConfirm={() => deleteMutation.mutate(kb.id)}
                >
                  <a>删除</a>
                </Popconfirm>,
              ]}
            >
              <div>Embedding 模型 ID：{kb.embedding_model_id}</div>
            </Card>
          </Col>
        ))}
      </Row>

      {selectedKb && (
        <Card
          title={`「${selectedKb.name}」的文档`}
          extra={
            <Upload
              showUploadList={false}
              beforeUpload={(file) => {
                uploadMutation.mutate({ kbId: selectedKb.id, file });
                return false;
              }}
            >
              <Button loading={uploadMutation.isPending}>上传文档</Button>
            </Upload>
          }
        >
          <Table
            dataSource={docPage?.items ?? []}
            rowKey="id"
            columns={[
              { title: '文件名', dataIndex: 'filename' },
              {
                title: '状态',
                dataIndex: 'status',
                render: (s: string) => (
                  <Tag color={STATUS_COLOR[s] ?? 'default'}>{s}</Tag>
                ),
              },
              { title: '字数', dataIndex: 'char_count' },
              {
                title: '错误',
                dataIndex: 'error',
                render: (e: string | null) => e ?? '-',
              },
            ]}
          />
        </Card>
      )}

      <Modal
        title="新建知识库"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={(v) => createMutation.mutate(v)}>
          <Form.Item name="name" label="知识库名" rules={[{ required: true }]}>
            <Input placeholder="如：产品文档" />
          </Form.Item>
          <Form.Item
            name="embedding_model_id"
            label="Embedding 模型"
            rules={[{ required: true }]}
          >
            <Select
              placeholder="选择 embedding 模型"
              options={embeddingModels.map((m) => ({ value: m.id, label: m.model_key }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
