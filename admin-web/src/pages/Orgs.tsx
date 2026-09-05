import { useCallback, useEffect, useState } from 'react';
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
  member_count?: number;
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

export default function Orgs() {
  const [status, setStatus] = useState('pending');
  const [list, setList] = useState<Org[]>([]);
  const [msg, setMsg] = useState('');

  const load = useCallback(() => {
    api.orgs(status).then(setList).catch((e: any) => setMsg(e.detail || '加载失败'));
  }, [status]);
  useEffect(load, [load]);

  const act = async (o: Org, action: 'approve' | 'reject') => {
    let reason = '';
    if (action === 'reject') {
      reason = prompt('驳回原因：') || '';
      if (!reason) return;
    } else if (!confirm(`通过「${o.name}」的创建申请？`)) {
      return;
    }
    try {
      await api.reviewOrg(o.id, { action, reason });
      load();
    } catch (e: any) {
      alert(e.detail || '操作失败');
    }
  };

  return (
    <div>
      <div className="page-title">组织审核</div>
      <div className="page-sub">
        仅审核「创建组织」申请。组织日常管理（邀请、审成员、下架）在小程序内由组织管理员完成。
      </div>

      <div className="tabs">
        {(['pending', 'approved', 'rejected', 'all'] as const).map((s) => (
          <button key={s} className={status === s ? 'active' : ''} onClick={() => setStatus(s)}>
            {s === 'all' ? '全部' : STATUS_TEXT[s]}
          </button>
        ))}
      </div>
      {msg && <div style={{ color: 'var(--red)', marginBottom: 10 }}>{msg}</div>}

      {list.map((o) => (
        <div className="card" key={o.id}>
          <div className="row">
            <b style={{ fontSize: 17 }}>{o.name}</b>
            <span className={'chip ' + (o.status === 'pending' ? 'red' : '')}>
              {STATUS_TEXT[o.status] || o.status}
            </span>
          </div>
          <div className="mt" style={{ color: 'var(--muted)', fontSize: 13 }}>
            {TYPE_TEXT[o.org_type] || o.org_type} · 申请人：{o.creator_name || '—'} · {o.created_at}
          </div>
          {o.description && <div className="mt">说明：{o.description}</div>}
          {o.reject_reason && <div className="mt">驳回原因：{o.reject_reason}</div>}
          {o.invite_code && <div className="mt">邀请码：<b>{o.invite_code}</b></div>}
          {o.status === 'pending' && (
            <div className="row mt">
              <button className="ghost" onClick={() => act(o, 'reject')}>驳回</button>
              <button onClick={() => act(o, 'approve')}>通过</button>
            </div>
          )}
        </div>
      ))}
      {list.length === 0 && <div className="empty">暂无{status === 'all' ? '' : STATUS_TEXT[status]}组织</div>}
    </div>
  );
}
