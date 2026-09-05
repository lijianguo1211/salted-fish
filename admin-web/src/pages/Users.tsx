import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

type User = { id: number; nickname: string; school: string; grade_class: string; role: string; coin_balance: number; is_active: boolean };

export default function Users() {
  const [keyword, setKeyword] = useState('');
  const [list, setList] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);

  const load = useCallback(() => {
    api.users({ keyword: keyword.trim(), page, page_size: 20 })
      .then((res: any) => { setList(res.users || []); setTotal(res.total || 0); })
      .catch(() => {});
  }, [keyword, page]);
  useEffect(load, [load]);

  const toggle = async (u: User) => {
    if (!confirm(`${u.is_active ? '停用' : '启用'}「${u.nickname}」？`)) return;
    try {
      await api.toggleUser(u.id);
      load();
    } catch (e: any) {
      alert(e.detail || '操作失败');
    }
  };

  return (
    <div>
      <div className="page-title">孩子 / 积分管理</div>
      <div className="page-sub">查看孩子账号与咸鱼币余额，可搜索、停用/启用账号（停用后无法登录）。</div>

      <div className="row" style={{ marginBottom: 16 }}>
        <input className="grow" placeholder="搜索昵称 / 班级（如：三年级2班）" value={keyword}
               onChange={(e) => { setKeyword(e.target.value); setPage(1); }} />
        <span style={{ color: 'var(--muted)', fontSize: 13 }}>共 {total} 个</span>
      </div>

      <table>
        <thead><tr><th>昵称</th><th>学校</th><th>班级</th><th>角色</th><th>咸鱼币</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>
          {list.map((u) => (
            <tr key={u.id}>
              <td><b>{u.nickname}</b></td>
              <td>{u.school || '—'}</td>
              <td>{u.grade_class || '—'}</td>
              <td>{u.role}</td>
              <td style={{ fontWeight: 700 }}>🐟 {u.coin_balance}</td>
              <td><span className={'chip ' + (u.is_active ? '' : 'gray')}>{u.is_active ? '正常' : '停用'}</span></td>
              <td>
                <button className={u.is_active ? 'danger' : ''} onClick={() => toggle(u)}>
                  {u.is_active ? '停用' : '启用'}
                </button>
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
      {list.length === 0 && <div className="empty">暂无孩子</div>}
    </div>
  );
}