import { useCallback, useEffect, useState } from 'react';
import {
  App, Button, Card, Form, Input, InputNumber, Modal, Space, Switch, Table, Tag, Typography,
} from 'antd';
import { api } from '../api';

type Llm = {
  id: number;
  name: string;
  vendor: string;
  base_url: string;
  api_key: string;
  api_key_set: boolean;
  model: string;
  is_active: boolean;
  sort_order: number;
  timeout_sec: number;
  note: string;
  last_error: string;
  last_ok_at: string;
  fail_count: number;
  support_text: boolean;
  support_image: boolean;
  support_audio: boolean;
};

type AiSettings = {
  ai_pricing_enabled: boolean;
  ai_moderation_enabled: boolean;
};

export default function Llms() {
  const { message, modal } = App.useApp();
  const [list, setList] = useState<Llm[]>([]);
  const [aiSettings, setAiSettings] = useState<AiSettings>({
    ai_pricing_enabled: true,
    ai_moderation_enabled: false,
  });
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([api.llmProviders(), api.aiSettings()])
      .then(([rows, settings]) => {
        setList(rows || []);
        if (settings) {
          setAiSettings({
            ai_pricing_enabled: !!settings.ai_pricing_enabled,
            ai_moderation_enabled: !!settings.ai_moderation_enabled,
          });
        }
      })
      .catch((e: any) => message.error(e.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [message]);
  useEffect(load, [load]);

  const saveAiSetting = async (patch: Partial<AiSettings>) => {
    const next = { ...aiSettings, ...patch };
    setAiSettings(next);
    try {
      const r = await api.updateAiSettings(patch);
      setAiSettings({
        ai_pricing_enabled: !!r.ai_pricing_enabled,
        ai_moderation_enabled: !!r.ai_moderation_enabled,
      });
      message.success('已更新 AI 开关');
    } catch (e: any) {
      message.error(e.detail || '更新失败');
      load();
    }
  };

  const openCreate = () => {
    setEditingId(null);
    form.setFieldsValue({
      name: '',
      vendor: '',
      base_url: '',
      api_key: '',
      model: '',
      is_active: true,
      sort_order: 0,
      timeout_sec: 30,
      support_text: true,
      support_image: true,
      support_audio: false,
      note: '',
    });
    setOpen(true);
  };

  const openEdit = (row: Llm) => {
    setEditingId(row.id);
    form.setFieldsValue({
      ...row,
      api_key: '',
    });
    setOpen(true);
  };

  const save = async () => {
    const values = await form.validateFields();
    try {
      if (editingId) {
        const body = { ...values };
        if (!body.api_key) delete body.api_key;
        await api.updateLlm(editingId, body);
      } else {
        if (!values.api_key?.trim()) {
          message.warning('新增时必须填 API Key');
          return;
        }
        await api.createLlm(values);
      }
      message.success('已保存');
      setOpen(false);
      load();
    } catch (e: any) {
      message.error(e.detail || '保存失败');
    }
  };

  const remove = async (row: Llm) => {
    const ok = await modal.confirm({ title: `删除「${row.name}」？` });
    if (!ok) return;
    try {
      await api.deleteLlm(row.id);
      message.success('已删除');
      load();
    } catch (e: any) {
      message.error(e.detail || '删除失败');
    }
  };

  const test = async (row: Llm) => {
    const hide = message.loading('测试连通中...', 0);
    try {
      const r = await api.testLlm(row.id);
      hide();
      message.success(`连通正常：${r.reply || 'ok'}`);
      load();
    } catch (e: any) {
      hide();
      message.error(e.detail || '连通失败');
      load();
    }
  };

  return (
    <div>
      <div className="admin-page-header">
        <Typography.Title level={3}>大模型管理</Typography.Title>
        <Typography.Paragraph type="secondary">
          配置多个 API Key（OpenAI 兼容）。开启下方能力后，估值与合规检测会按优先级依次尝试模型；
          估值失败回退规则引擎，合规检测开启后失败则拒绝上架。
        </Typography.Paragraph>
      </div>

      <Card size="small" title="AI 能力开关" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size={16} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 240 }}>
              <Typography.Text strong>AI 估值（价值评估）</Typography.Text>
              <div style={{ color: 'rgba(0,0,0,0.45)', fontSize: 13, marginTop: 4 }}>
                开启后，上架估价优先用支持图像的大模型；关闭则仅用规则引擎。
              </div>
            </div>
            <Switch
              checked={aiSettings.ai_pricing_enabled}
              onChange={(v) => saveAiSetting({ ai_pricing_enabled: v })}
              checkedChildren="开"
              unCheckedChildren="关"
            />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 240 }}>
              <Typography.Text strong>AI 合规检测（合法性）</Typography.Text>
              <div style={{ color: 'rgba(0,0,0,0.45)', fontSize: 13, marginTop: 4 }}>
                开启后，上架/修改闲置必须过检；拦截违法违规、不利于学生的内容。需至少配置一台可用文本模型。
              </div>
            </div>
            <Switch
              checked={aiSettings.ai_moderation_enabled}
              onChange={(v) => saveAiSetting({ ai_moderation_enabled: v })}
              checkedChildren="开"
              unCheckedChildren="关"
            />
          </div>
        </Space>
      </Card>

      <Button type="primary" onClick={openCreate} style={{ marginBottom: 16 }}>
        新增配置
      </Button>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={list}
        scroll={{ x: 1100 }}
        pagination={false}
        columns={[
          { title: '优先', dataIndex: 'sort_order', width: 70 },
          {
            title: '名称',
            dataIndex: 'name',
            render: (v, row) => (
              <div>
                <b>{v}</b>
                <div style={{ color: 'rgba(0,0,0,0.45)', fontSize: 12 }}>{row.base_url}</div>
                {row.last_error && (
                  <div style={{ color: '#e5484d', fontSize: 12 }}>{row.last_error}</div>
                )}
              </div>
            ),
          },
          { title: '厂商', dataIndex: 'vendor', width: 110 },
          { title: '模型', dataIndex: 'model', ellipsis: true },
          {
            title: '输入',
            dataIndex: 'support_image',
            width: 110,
            render: (_img, row) => {
              const tags = [];
              if (row.support_text !== false) tags.push('文');
              if (row.support_image) tags.push('图');
              if (row.support_audio) tags.push('音');
              return tags.length ? tags.join('/') : '—';
            },
          },
          {
            title: 'Key',
            dataIndex: 'api_key',
            width: 140,
            render: (v) => <Typography.Text code>{v || '—'}</Typography.Text>,
          },
          {
            title: '状态',
            dataIndex: 'is_active',
            width: 80,
            render: (v) => <Tag color={v ? 'success' : 'default'}>{v ? '启用' : '停用'}</Tag>,
          },
          { title: '最近成功', dataIndex: 'last_ok_at', width: 140, render: (v) => v || '—' },
          { title: '失败', dataIndex: 'fail_count', width: 70 },
          {
            title: '操作',
            fixed: 'right',
            width: 220,
            render: (_, row) => (
              <Space wrap>
                <Button size="small" onClick={() => test(row)}>测试</Button>
                <Button size="small" onClick={() => openEdit(row)}>编辑</Button>
                <Button size="small" danger onClick={() => remove(row)}>删除</Button>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editingId ? '编辑配置' : '新增配置'}
        open={open}
        onOk={save}
        onCancel={() => setOpen(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="vendor"
            label="厂商"
            rules={[{ required: true, message: '请填写厂商，如 OpenAI / 硅基流动 / 自建网关' }]}
            extra="自行填写即可，如 OpenAI、DeepSeek、硅基流动、自建网关等"
          >
            <Input placeholder="例如：硅基流动" maxLength={32} />
          </Form.Item>
          <Form.Item name="name" label="显示名" rules={[{ required: true, message: '请填写显示名' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL" rules={[{ required: true, message: '请填写 Base URL' }]}>
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>
          <Form.Item
            name="api_key"
            label={editingId ? 'API Key（留空不改）' : 'API Key'}
            rules={editingId ? [] : [{ required: true, message: '请填写 API Key' }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item name="model" label="模型名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space wrap style={{ width: '100%' }} size="large">
            <Form.Item name="sort_order" label="优先级（越小越先）">
              <InputNumber style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="timeout_sec" label="超时（秒）">
              <InputNumber min={5} max={120} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="is_active" label="启用" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item label="支持输入" style={{ marginBottom: 4 }}>
            <Space wrap size={16}>
              <Form.Item name="support_text" valuePropName="checked" noStyle>
                <Switch checkedChildren="文本" unCheckedChildren="文本" />
              </Form.Item>
              <Form.Item name="support_image" valuePropName="checked" noStyle>
                <Switch checkedChildren="图像/多模态" unCheckedChildren="图像/多模态" />
              </Form.Item>
              <Form.Item name="support_audio" valuePropName="checked" noStyle>
                <Switch checkedChildren="音频" unCheckedChildren="音频" />
              </Form.Item>
            </Space>
            <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginTop: 4 }}>
              「图像/多模态」用于照片估值；「文本」用于合规检测。建议至少保留一台文本模型。
            </div>
          </Form.Item>
          <Form.Item name="note" label="备注">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
