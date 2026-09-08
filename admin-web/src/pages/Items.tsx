import { useCallback, useEffect, useState } from 'react';
import { App, Button, Input, Select, Space, Table, Tag, Typography } from 'antd';
import { api } from '../api';

type Item = {
  id: number;
  name: string;
  category: string;
  owner: string;
  owner_class?: string;
  value_coins: number;
  ai_value_coins?: number;
  status: string;
  reported?: number;
  flagged?: boolean;
};

const STATUS: Record<string, string> = {
  on_shelf: '在售',
  swapping: '交换中',
  swapped: '已换出',
  off_shelf: '已下架',
  removed: '已删除',
};

export default function Items() {
  const { message, modal } = App.useApp();
  const [status, setStatus] = useState('all');
  const [keyword, setKeyword] = useState('');
  const [list, setList] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api.items({ status, keyword: keyword.trim(), page, page_size: 20 })
      .then((res: any) => {
        setList(res.items || []);
        setTotal(res.total || 0);
      })
      .catch((e: any) => message.error(e.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [status, keyword, page, message]);
  useEffect(load, [load]);

  const setSt = async (it: Item, s: string) => {
    if (s === 'removed') {
      const ok = await modal.confirm({ title: `确认下架「${it.name}」？` });
      if (!ok) return;
    }
    try {
      await api.setItemStatus(it.id, s);
      message.success('已更新');
      load();
    } catch (e: any) {
      message.error(e.detail || '操作失败');
    }
  };

  return (
    <div>
      <div className="admin-page-header">
        <Typography.Title level={3}>物品管理</Typography.Title>
        <Typography.Paragraph type="secondary">
          浏览全部闲置，关键词搜索、按状态筛选，可直接下架违规物品。
        </Typography.Paragraph>
      </div>

      <Space wrap style={{ marginBottom: 16, width: '100%' }}>
        <Select
          value={status}
          style={{ width: 140 }}
          onChange={(v) => { setStatus(v); setPage(1); }}
          options={[
            { value: 'all', label: '全部' },
            { value: 'on_shelf', label: '在售' },
            { value: 'off_shelf', label: '已下架' },
            { value: 'removed', label: '已删除' },
          ]}
        />
        <Input.Search
          allowClear
          placeholder="搜索物品名"
          style={{ width: 260, maxWidth: '100%' }}
          onSearch={(v) => { setKeyword(v); setPage(1); }}
        />
        <Typography.Text type="secondary">共 {total} 件</Typography.Text>
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
          { title: '物品', dataIndex: 'name', render: (v) => <b>{v}</b> },
          { title: '分类', dataIndex: 'category' },
          {
            title: '物主',
            render: (_, it) => (
              <span>
                {it.owner}{' '}
                <Typography.Text type="secondary">{it.owner_class}</Typography.Text>
              </span>
            ),
          },
          { title: '物主估值', dataIndex: 'value_coins', render: (v) => `🐟 ${v}` },
          { title: 'AI估值', dataIndex: 'ai_value_coins', render: (v) => (v ? `🐟 ${v}` : '—') },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s) => (
              <Tag color={s === 'on_shelf' ? 'success' : 'default'}>{STATUS[s] || s}</Tag>
            ),
          },
          {
            title: '举报',
            render: (_, it) => `${it.reported || 0}${it.flagged ? ' ⚠️' : ''}`,
          },
          {
            title: '操作',
            fixed: 'right',
            width: 160,
            render: (_, it) => (
              <Space>
                {it.status !== 'removed' && (
                  <Button danger size="small" onClick={() => setSt(it, 'removed')}>下架</Button>
                )}
                {it.status === 'off_shelf' && (
                  <Button size="small" onClick={() => setSt(it, 'on_shelf')}>恢复</Button>
                )}
              </Space>
            ),
          },
        ]}
      />
    </div>
  );
}
