import { useCallback, useEffect, useState } from 'react';
import { App, Button, Form, Input, InputNumber, Modal, Space, Switch, Table, Tag, Typography } from 'antd';
import { api } from '../api';

type Category = {
  id: number;
  name: string;
  value_base: number;
  note: string;
  sort_order: number;
  is_active: boolean;
};

export default function Categories() {
  const { message, modal } = App.useApp();
  const [list, setList] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [form] = Form.useForm();

  const load = useCallback(() => {
    setLoading(true);
    api.categories()
      .then(setList)
      .catch((e: any) => message.error(e.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [message]);
  useEffect(load, [load]);

  const openCreate = () => {
    setEditing(null);
    form.setFieldsValue({ name: '', value_base: 2, note: '', sort_order: 0, is_active: true });
    setOpen(true);
  };

  const openEdit = (c: Category) => {
    setEditing(c);
    form.setFieldsValue(c);
    setOpen(true);
  };

  const save = async () => {
    const values = await form.validateFields();
    try {
      if (editing) await api.updateCategory(editing.id, values);
      else await api.createCategory(values);
      message.success('已保存');
      setOpen(false);
      load();
    } catch (e: any) {
      message.error(e.detail || '保存失败');
    }
  };

  const remove = async (c: Category) => {
    const ok = await modal.confirm({
      title: `删除分类「${c.name}」？`,
      content: '若有闲置正在使用将无法删除。',
    });
    if (!ok) return;
    try {
      await api.deleteCategory(c.id);
      message.success('已删除');
      load();
    } catch (e: any) {
      message.error(e.detail || '删除失败');
    }
  };

  return (
    <div>
      <div className="admin-page-header">
        <Typography.Title level={3}>分类管理</Typography.Title>
        <Typography.Paragraph type="secondary">
          闲置分类存数据库，可新增 / 改名 / 调估值基准 / 排序 / 启停。停用后发布时不可选。
        </Typography.Paragraph>
      </div>

      <Button type="primary" onClick={openCreate} style={{ marginBottom: 16 }}>
        新增分类
      </Button>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={list}
        scroll={{ x: 720 }}
        pagination={false}
        columns={[
          { title: '#', width: 60, render: (_, __, i) => i + 1 },
          { title: '分类名', dataIndex: 'name', render: (v) => <b>{v}</b> },
          { title: '估值基准', dataIndex: 'value_base', render: (v) => `${v} 枚` },
          { title: '排序', dataIndex: 'sort_order' },
          {
            title: '状态',
            dataIndex: 'is_active',
            render: (v) => <Tag color={v ? 'success' : 'default'}>{v ? '启用' : '停用'}</Tag>,
          },
          { title: '说明', dataIndex: 'note', ellipsis: true },
          {
            title: '操作',
            fixed: 'right',
            width: 160,
            render: (_, c) => (
              <Space>
                <Button size="small" onClick={() => openEdit(c)}>编辑</Button>
                <Button size="small" danger onClick={() => remove(c)}>删除</Button>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? '编辑分类' : '新增分类'}
        open={open}
        onOk={save}
        onCancel={() => setOpen(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="分类名" rules={[{ required: true, message: '请填写分类名' }]}>
            <Input />
          </Form.Item>
          <Form.Item name="value_base" label="AI 估值基准枚数" rules={[{ required: true }]}>
            <InputNumber min={1} max={15} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="sort_order" label="排序（越小越靠前）">
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="note" label="说明">
            <Input />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
