import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

type Item = { id: number; name: string; category: string; owner: string; owner_class?: string; value_coins: number; status: string; reported?: number; flagged?: boolean };

const STATUS: Record<string, string> = {
  on_shelf: '在售', swapping: '交换中', swapped: '已换出', off_shelf: '已下架', removed: '已删除',
};

export default function Items() {
  const [status, setStatus] = useState('all');
  const [keyword, setKeyword] = useState('');
  const [list, setList] = useState<Item[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [msg, setMsg] = useState('');

  const load = useCallback(() => {
    api.items({ status, keyword: keyword.trim(), page, page_size: 20 })
      .then((res: any) => { setList(res.items || []); setTotal(res.total || 0); })
      .catch((e: any) => setMsg(e.detail || '加载失败'));
  }, [status, keyword, page]);
  useEffect(load, [load]);

  const setSt = async (it: Item, s: string) => {
    if (s === 'removed' && !confirm(`确认下架「${it.name}」？`)) return;
    try {
      await api.setItemStatus(it.id, s);
      load();
    } catch (e: any) {
      alert(e.detail || '操作失败');
    }
  };

  return (
    <div>
      <div className="page-title">物品管理</div>
      <div className="page-sub">浏览全部闲置，关键词搜索、按状态筛选，可直接下架违规物品。</div>

      <div className="row" style={{ marginBottom: 16 }}>
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="all">全部</option>
          <option value="on_shelf">在售</option>
          <option value="off_shelf">已下架</option>
          <option value="removed">已删除</option>
        </select>
        <input className="grow" placeholder="搜索物品名" value={keyword}
               onChange={(e) => { setKeyword(e.target.value); setPage(1); }} />
        <span style={{ color: 'var(--muted)', fontSize: 13 }}>共 {total} 件</span>
      </div>
      {msg && <div style={{ color: 'var(--red)', marginBottom: 10 }}>{msg}</div>}

      <table>
        <thead><tr><th>物品</th><th>分类</th><th>物主</th><th>估值</th><th>状态</th><th>举报</th><th>操作</th></tr></thead>
        <tbody>
          {list.map((it) => (
            <tr key={it.id}>
              <td><b>{it.name}</b></td>
              <td>{it.category}</td>
              <td>{it.owner}<span style={{ color: 'var(--muted)' }}> {it.owner_class}</span></td>
              <td>🐟 {it.value_coins}</td>
              <td><span className={'chip ' + (it.status === 'on_shelf' ? '' : 'gray')}>{STATUS[it.status] || it.status}</span></td>
              <td>{it.reported || 0}{it.flagged ? ' ⚠️' : ''}</td>
              <td>
                {it.status !== 'removed' && (
                  <button className="danger" onClick={() => setSt(it, 'removed')}>下架</button>
                )}
                {it.status === 'off_shelf' && (
                  <button className="ghost" style={{ marginLeft: 6 }} onClick={() => setSt(it, 'on_shelf')}>恢复</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="row" style={{ marginTop: 16, justifyContent: 'flex-end' }}>
        <button className="ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
        <span style={{ color: 'var(--muted)', fontSize: 13 }}>第 {page} 页</span>
        <button className="ghost" disabled={page * 20 >= total} onClick={() => setPage(page + 1)}>下一页</button>
      </div>
      {list.length === 0 && <div className="empty">暂无物品</div>}
    </div>
  );
}