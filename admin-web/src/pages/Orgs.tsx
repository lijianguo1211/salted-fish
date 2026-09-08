import { useCallback, useEffect, useState } from 'react';
import {
  App,
  Button,
  Card,
  Empty,
  Image,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Space,
  Tag,
  Typography,
} from 'antd';
import { api } from '../api';

type Org = {
  id: number;
  name: string;
  org_type: string;
  description: string;
  status: string;
  creator_name: string;
  reject_reason: string;
  invite_code?: string;
  created_at: string;
};

type QuotaApp = {
  id: number;
  user_id: number;
  nickname: string;
  reason: string;
  proof_urls: string[];
  requested_limit: number;
  status: string;
  reject_reason: string;
  created_at: string;
};

const STATUS_TEXT: Record<string, string> = {
  pending: '待审核',
  approved: '已通过',
  rejected: '已驳回',
};

const TYPE_TEXT: Record<string, string> = {
  school: '学校',
  community: '小区',
  other: '其他',
};

const API_BASE = (import.meta.env.VITE_API_BASE as string) || '/api';

function proofSrc(url: string) {
  if (!url) return '';
  if (url.startsWith('http')) return url;
  return `${API_BASE.replace(/\/$/, '')}${url.startsWith('/') ? '' : '/'}${url}`;
}

export default function Orgs() {
  const { message, modal } = App.useApp();
  const [tab, setTab] = useState<'orgs' | 'quota' | 'settings'>('orgs');
  const [status, setStatus] = useState('pending');
  const [list, setList] = useState<Org[]>([]);
  const [quotaList, setQuotaList] = useState<QuotaApp[]>([]);
  const [quotaStatus, setQuotaStatus] = useState('pending');
  const [maxOrgs, setMaxOrgs] = useState<number>(3);
  const [loading, setLoading] = useState(false);

  const loadOrgs = useCallback(() => {
    setLoading(true);
    api.orgs(status)
      .then(setList)
      .catch((e: any) => message.error(e.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [status, message]);

  const loadQuota = useCallback(() => {
    setLoading(true);
    api.orgQuotaApps(quotaStatus)
      .then(setQuotaList)
      .catch((e: any) => message.error(e.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [quotaStatus, message]);

  const loadSettings = useCallback(() => {
    api.orgSettings()
      .then((s: any) => setMaxOrgs(s.max_orgs_per_creator || 3))
      .catch((e: any) => message.error(e.detail || '加载设置失败'));
  }, [message]);

  useEffect(() => {
    if (tab === 'orgs') loadOrgs();
    else if (tab === 'quota') loadQuota();
    else loadSettings();
  }, [tab, loadOrgs, loadQuota, loadSettings]);

  const act = async (o: Org, action: 'approve' | 'reject') => {
    if (action === 'approve') {
      const ok = await modal.confirm({ title: `通过「${o.name}」的创建申请？` });
      if (!ok) return;
      try {
        await api.reviewOrg(o.id, { action, reason: '' });
        message.success('已通过');
        loadOrgs();
      } catch (e: any) {
        message.error(e.detail || '操作失败');
      }
      return;
    }

    let reason = '';
    Modal.confirm({
      title: '驳回原因',
      content: (
        <Input.TextArea
          rows={3}
          placeholder="请填写驳回原因"
          onChange={(e) => { reason = e.target.value; }}
        />
      ),
      onOk: async () => {
        if (!reason.trim()) {
          message.warning('请填写驳回原因');
          return Promise.reject();
        }
        try {
          await api.reviewOrg(o.id, { action: 'reject', reason: reason.trim() });
          message.success('已驳回');
          loadOrgs();
        } catch (e: any) {
          message.error(e.detail || '操作失败');
          return Promise.reject();
        }
      },
    });
  };

  const actQuota = async (row: QuotaApp, action: 'approve' | 'reject') => {
    if (action === 'approve') {
      const ok = await modal.confirm({
        title: `通过提额？将把「${row.nickname}」可创建上限设为 ${row.requested_limit}`,
      });
      if (!ok) return;
      try {
        await api.reviewOrgQuota(row.id, { action: 'approve', reason: '' });
        message.success('已通过提额');
        loadQuota();
      } catch (e: any) {
        message.error(e.detail || '操作失败');
      }
      return;
    }
    let reason = '';
    Modal.confirm({
      title: '驳回提额申请',
      content: (
        <Input.TextArea
          rows={3}
          placeholder="驳回原因"
          onChange={(e) => { reason = e.target.value; }}
        />
      ),
      onOk: async () => {
        try {
          await api.reviewOrgQuota(row.id, { action: 'reject', reason: reason.trim() });
          message.success('已驳回');
          loadQuota();
        } catch (e: any) {
          message.error(e.detail || '操作失败');
          return Promise.reject();
        }
      },
    });
  };

  const saveSettings = async () => {
    try {
      const s = await api.updateOrgSettings({ max_orgs_per_creator: maxOrgs });
      setMaxOrgs(s.max_orgs_per_creator);
      message.success('已保存默认额度');
    } catch (e: any) {
      message.error(e.detail || '保存失败');
    }
  };

  return (
    <div>
      <div className="admin-page-header">
        <Typography.Title level={3}>组织审核</Typography.Title>
        <Typography.Paragraph type="secondary">
          审核创建组织、配置每人默认可创建数量，并处理超额提额申请（需原因与证明材料）。
        </Typography.Paragraph>
      </div>

      <Segmented
        value={tab}
        onChange={(v) => setTab(v as any)}
        options={[
          { label: '创建申请', value: 'orgs' },
          { label: '提额申请', value: 'quota' },
          { label: '额度配置', value: 'settings' },
        ]}
        style={{ marginBottom: 16 }}
      />

      {tab === 'settings' && (
        <Card title="每人默认可创建组织数">
          <Space wrap align="center">
            <InputNumber min={1} max={50} value={maxOrgs} onChange={(v) => setMaxOrgs(Number(v || 3))} />
            <Button type="primary" onClick={saveSettings}>保存</Button>
          </Space>
          <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
            默认建议 3。超出后用户需在小程序提交原因说明，并上传教师资格证等证明，由本页「提额申请」审核通过后生效。
          </Typography.Paragraph>
        </Card>
      )}

      {tab === 'quota' && (
        <>
          <Segmented
            value={quotaStatus}
            onChange={(v) => setQuotaStatus(String(v))}
            options={[
              { label: '待审核', value: 'pending' },
              { label: '已通过', value: 'approved' },
              { label: '已驳回', value: 'rejected' },
              { label: '全部', value: 'all' },
            ]}
            style={{ marginBottom: 16 }}
          />
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {quotaList.map((row) => (
              <Card
                key={row.id}
                loading={loading}
                title={
                  <Space wrap>
                    <span>{row.nickname || `用户#${row.user_id}`}</span>
                    <Tag>申请上限 {row.requested_limit}</Tag>
                    <Tag color={row.status === 'pending' ? 'error' : row.status === 'approved' ? 'success' : 'default'}>
                      {STATUS_TEXT[row.status] || row.status}
                    </Tag>
                  </Space>
                }
                extra={
                  row.status === 'pending' ? (
                    <Space wrap>
                      <Button onClick={() => actQuota(row, 'reject')}>驳回</Button>
                      <Button type="primary" onClick={() => actQuota(row, 'approve')}>通过</Button>
                    </Space>
                  ) : null
                }
              >
                <div style={{ color: 'rgba(0,0,0,0.45)', fontSize: 13 }}>{row.created_at}</div>
                <div style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>原因：{row.reason}</div>
                {row.reject_reason && <div style={{ marginTop: 8 }}>驳回：{row.reject_reason}</div>}
                {!!row.proof_urls?.length && (
                  <Image.PreviewGroup>
                    <Space wrap style={{ marginTop: 12 }}>
                      {row.proof_urls.map((u) => (
                        <Image key={u} width={88} height={88} src={proofSrc(u)} style={{ objectFit: 'cover' }} />
                      ))}
                    </Space>
                  </Image.PreviewGroup>
                )}
              </Card>
            ))}
            {!loading && quotaList.length === 0 && (
              <Empty description={`暂无${quotaStatus === 'all' ? '' : STATUS_TEXT[quotaStatus]}提额申请`} />
            )}
          </Space>
        </>
      )}

      {tab === 'orgs' && (
        <>
          <Segmented
            value={status}
            onChange={(v) => setStatus(String(v))}
            options={[
              { label: '待审核', value: 'pending' },
              { label: '已通过', value: 'approved' },
              { label: '已驳回', value: 'rejected' },
              { label: '全部', value: 'all' },
            ]}
            style={{ marginBottom: 16 }}
          />

          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            {list.map((o) => (
              <Card
                key={o.id}
                loading={loading}
                title={
                  <Space wrap>
                    <span>{o.name}</span>
                    <Tag color={o.status === 'pending' ? 'error' : o.status === 'approved' ? 'success' : 'default'}>
                      {STATUS_TEXT[o.status] || o.status}
                    </Tag>
                  </Space>
                }
                extra={
                  o.status === 'pending' ? (
                    <Space wrap>
                      <Button onClick={() => act(o, 'reject')}>驳回</Button>
                      <Button type="primary" onClick={() => act(o, 'approve')}>通过</Button>
                    </Space>
                  ) : null
                }
              >
                <div style={{ color: 'rgba(0,0,0,0.45)', fontSize: 13 }}>
                  {TYPE_TEXT[o.org_type] || o.org_type} · 申请人：{o.creator_name || '—'} · {o.created_at}
                </div>
                {o.description && <div style={{ marginTop: 8 }}>说明：{o.description}</div>}
                {o.reject_reason && <div style={{ marginTop: 8 }}>驳回原因：{o.reject_reason}</div>}
                {o.invite_code && (
                  <div style={{ marginTop: 8 }}>
                    邀请码：<Typography.Text code copyable>{o.invite_code}</Typography.Text>
                  </div>
                )}
              </Card>
            ))}
            {!loading && list.length === 0 && (
              <Empty description={`暂无${status === 'all' ? '' : STATUS_TEXT[status]}组织`} />
            )}
          </Space>
        </>
      )}
    </div>
  );
}
