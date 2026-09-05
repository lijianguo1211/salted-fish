import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

type Report = { id: number; item_id: number; reporter_name: string; reason: string; reporter_note: string; status: string; created_at: string; status_text?: string; item?: any };

const STATUS_TEXT: Record<string, string> = {
  pending: '待处理', resolved: '已下架', rejected: '已驳回', keep: '已保留',
};

export default function Reports() {
  const [status, setStatus] = useState('pending');
  const [list, setList] = useState<Report[]>([]);
  const [msg, setMsg] = useState('');

  const load = useCallback(() => {
    api.reports(status).then(setList).catch((e: any) => setMsg(e.detail || '加载失败'));
  }, [status]);
  useEffect(load, [load]);

  const act = async (r: Report, action: 'reject' | 'remove') => {
    const reason = action === 'remove'
      ? prompt('填下架原因（家长可见）：') || '经管理员审核，内容不合规已下架'
      : '管理员已核实，驳回举报';
    if (!reason) return;
    try {
      await api.handleReport(r.id, { action, reason });
      load();
    } catch (e: any) {
      alert(e.detail || '操作失败');
    }
  };

  return (
    <div>
      <div className="page-title">举报处理</div>
      <div className="page-sub">查看被举报内容，决定下架或驳回。物品被举报后仍可见（举报即公示），由管理员审理。</div>

      <div className="tabs">
        {(['pending', 'rejected', 'resolved'] as const).map((s) => (
          <button key={s} className={status === s ? 'active' : ''} onClick={() => setStatus(s)}>
            {STATUS_TEXT[s]}
          </button>
        ))}
      </div>
      {msg && <div style={{ color: 'var(--red)', marginBottom: 10 }}>{msg}</div>}

      {list.map((r) => (
        <div className="card" key={r.id}>
          <div className="row">
            <b style={{ fontSize: 17 }}>{r.item?.name || '（物品已删除）'}</b>
            <span className={'chip ' + (r.status === 'pending' ? 'red' : '')}>{STATUS_TEXT[r.status] || r.status}</span>
          </div>
          {r.item && <div className="mt" style={{ color: 'var(--muted)', fontSize: 13 }}>
            物主：{r.item.owner || '?'} · {r.item.owner_class || ''}
          </div>}
          <div className="mt">理由：{r.reason}</div>
          {r.reporter_note && <div className="mt">补充说明：{r.reporter_note}</div>}
          <div className="mt" style={{ color: 'var(--muted)', fontSize: 13 }}>
            {r.created_at} · {r.reporter_name} 上报
          </div>
          <div className="row mt">
            <button className="ghost" onClick={() => act(r, 'reject')} disabled={r.status !== 'pending'}>驳回（物品保留）</button>
            <button className="danger" onClick={() => act(r, 'remove')} disabled={r.status !== 'pending'}>下架</button>
          </div>
        </div>
      ))}
      {list.length === 0 && <div className="empty">暂无{STATUS_TEXT[status]}的举报</div>}
    </div>
  );
}