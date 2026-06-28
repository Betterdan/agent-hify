import { Button, Card, Form, Input, message } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { ApiError, request } from '@/lib/api/http';
import { setToken } from '@/lib/auth/token';

interface LoginValues {
  email: string;
  password: string;
}
interface TokenData {
  access_token: string;
  token_type: string;
}

export function LoginPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  async function onFinish(values: LoginValues) {
    setLoading(true);
    try {
      const data = await request<TokenData>({
        url: '/api/v1/auth/login',
        method: 'post',
        data: values,
      });
      setToken(data.access_token);
      navigate('/models', { replace: true });
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : '登录失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 120 }}>
      <Card title="agent-hify 登录" style={{ width: 360 }}>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item label="邮箱" name="email" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block aria-label="登录">
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
