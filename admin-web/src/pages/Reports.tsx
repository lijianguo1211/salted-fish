import { useCallback, useEffect, useState } from 'react';
import { App, Button, Card, Empty, Space, Tag, Typography, Segmented } from 'antd';
import { api } from '../api';

type Report = {
  id: number;
  item_id: number;
  reporter_name: string;
  reason: string;
  reporter_note: string;
  status: string;
  created_at: string;
  item?: any;
};

const STATUS_TEXT: Record<string, string> = {
  pending: '待处理',
  resolved: '已下架',
  rejected: '已驳回',
  keep: '已保留',
};

export default function Reports() {
  const { message, modal } = App.useApp();
  const [status, setStatus] = useState('pending');
  const [list, setList] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api.reports(status)
      .then(setList)
      .catch((e: any) => message.error(e.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [status, message]);
  useEffect(load, [load]);

  const act = async (r: Report, action: 'reject' | 'remove') => {
    if (action === 'remove') {
      const ok = await modal.confirm({
        title: '确认下架？',
        content: '将使用默认原因通知家长：经管理员审核，内容不合规已下架',
      });
      if (!ok) return;
      try {
        await api.handleReport(r.id, {
          action,
          reason: '经管理员审核，内容不合规已下架',
        });
        message.success('已下架');
        load();
      } catch (e: any) {
        message.error(e.detail || '操作失败');
      }
      return;
    }
    try {
      await api.handleReport(r.id, { action: 'reject', reason: '管理员已核实，驳回举报' });
      message.success('已驳回');
      load();
    } catch (e: any) {
      message.error(e.detail || '操作失败');
    }
  };

  return (
    <div>
      <div className="admin-page-header">
        <Typography.Title level={3}>举报处理</Typography.Title>
        <Typography.Paragraph type="secondary">
          查看被举报内容，决定下架或驳回。物品被举报后仍可见（举报即公示），由管理员审理。
        </Typography.Paragraph>
      </div>

      <Segmented
        value={status}
        onChange={(v) => setStatus(String(v))}
        options={[
          { label: '待处理', value: 'pending' },
          { label: '已驳回', value: 'rejected' },
          { label: '已下架', value: 'resolved' },
        ]}
        style={{ marginBottom: 16 }}
      />

      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {list.map((r) => (
          <Card
            key={r.id}
            loading={loading}
            title={
              <Space wrap>
                <span>{r.item?.name || '（物品已删除）'}</span>
                <Tag color={r.status === 'pending' ? 'error' : 'default'}>
                  {STATUS_TEXT[r.status] || r.status}
                </Tag>
              </Space>
            }
            extra={
              r.status === 'pending' ? (
                <Space wrap>
                  <Button onClick={() => act(r, 'reject')}>驳回（物品保留）</Button>
                  <Button danger type="primary" onClick={() => act(r, 'remove')}>下架</Button>
                </Space>
              ) : null
            }
          >
            {r.item && (
              <div style={{ marginBottom: 8, color: 'rgba(0,0,0,0.45)' }}>
                物主：{r.item.owner || '?'} · {r.item.owner_class || ''}
              </div>
            )}
            <div>理由：{r.reason}</div>
            {r.reporter_note && <div style={{ marginTop: 8 }}>补充说明：{r.reporter_note}</div>}
            <div style={{ marginTop: 8, color: 'rgba(0,0,0,0.45)', fontSize: 13 }}>
              {r.created_at} · {r.reporter_name} 上报
            </div>
          </Card>
        ))}
        {!loading && list.length === 0 && (
          <Empty description={`暂无${STATUS_TEXT[status]}的举报`} />
        )}
      </Space>
    </div>
  );
}
