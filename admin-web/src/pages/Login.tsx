import { useState } from 'react';
import { Button, Card, Form, Input, Typography, App } from 'antd';
import { api } from '../api';
import { setAuth } from '../api/client';
import { rsaEncryptPassword } from '../api/crypto';

export default function Login({ onAuth }: { onAuth: () => void }) {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);

  const submit = async (values: { email: string; password: string }) => {
    setLoading(true);
    try {
      const pk = await api.publicKey();
      const encrypted = await rsaEncryptPassword(pk.public_key, values.password);
      const res = await api.login(values.email, encrypted);
      setAuth(res.token, res.admin);
      onAuth();
    } catch (e: any) {
      message.error(e.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <Card>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          🥇 咸鱼小市场
        </Typography.Title>
        <Typography.Paragraph type="secondary">独立管理后台 · 管理员登录</Typography.Paragraph>
        <Form layout="vertical" onFinish={submit} requiredMark={false}>
          <Form.Item name="email" label="管理员邮箱" rules={[{ required: true, message: '请填写邮箱' }]}>
            <Input size="large" placeholder="admin@example.com" autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请填写密码' }]}>
            <Input.Password size="large" placeholder="请输入密码" autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large" loading={loading}>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
