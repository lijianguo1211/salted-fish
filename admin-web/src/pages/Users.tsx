import { useCallback, useEffect, useState } from 'react';
import { App, Button, Input, Space, Table, Tag, Typography } from 'antd';
import { api } from '../api';

type User = {
  id: number;
  nickname: string;
  school: string;
  grade_class: string;
  role: string;
  coin_balance: number;
  is_active: boolean;
};

export default function Users() {
  const { message, modal } = App.useApp();
  const [keyword, setKeyword] = useState('');
  const [list, setList] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api.users({ keyword: keyword.trim(), page, page_size: 20 })
      .then((res: any) => {
        setList(res.users || []);
        setTotal(res.total || 0);
      })
      .catch((e: any) => message.error(e.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [keyword, page, message]);
  useEffect(load, [load]);

  const toggle = async (u: User) => {
    const ok = await modal.confirm({
      title: `${u.is_active ? '停用' : '启用'}「${u.nickname}」？`,
      content: u.is_active ? '停用后无法登录。' : undefined,
    });
    if (!ok) return;
    try {
      await api.toggleUser(u.id);
      message.success('已更新');
      load();
    } catch (e: any) {
      message.error(e.detail || '操作失败');
    }
  };

  return (
    <div>
      <div className="admin-page-header">
        <Typography.Title level={3}>孩子 / 积分管理</Typography.Title>
        <Typography.Paragraph type="secondary">
          查看孩子账号与咸鱼币余额，可搜索、停用/启用账号（停用后无法登录）。
        </Typography.Paragraph>
      </div>

      <Space wrap style={{ marginBottom: 16 }}>
        <Input.Search
          allowClear
          placeholder="搜索昵称 / 班级"
          style={{ width: 280, maxWidth: '100%' }}
          onSearch={(v) => { setKeyword(v); setPage(1); }}
        />
        <Typography.Text type="secondary">共 {total} 个</Typography.Text>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={list}
        scroll={{ x: 800 }}
        pagination={{
          current: page,
          pageSize: 20,
          total,
          onChange: setPage,
          showSizeChanger: false,
        }}
        columns={[
          { title: '昵称', dataIndex: 'nickname', render: (v) => <b>{v}</b> },
          { title: '学校', dataIndex: 'school', render: (v) => v || '—' },
          { title: '班级', dataIndex: 'grade_class', render: (v) => v || '—' },
          { title: '角色', dataIndex: 'role' },
          {
            title: '咸鱼币',
            dataIndex: 'coin_balance',
            render: (v) => <b>🐟 {v}</b>,
          },
          {
            title: '状态',
            dataIndex: 'is_active',
            render: (v) => <Tag color={v ? 'success' : 'default'}>{v ? '正常' : '停用'}</Tag>,
          },
          {
            title: '操作',
            fixed: 'right',
            width: 100,
            render: (_, u) => (
              <Button
                size="small"
                danger={u.is_active}
                onClick={() => toggle(u)}
              >
                {u.is_active ? '停用' : '启用'}
              </Button>
            ),
          },
        ]}
      />
    </div>
  );
}
