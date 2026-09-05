import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

type Category = { id: number; name: string; value_base: number; note: string; sort_order: number; is_active: boolean };

const EMPTY = { name: '', value_base: 2, note: '', sort_order: 0, is_active: true };

export default function Categories() {
  const [list, setList] = useState<Category[]>([]);
  const [editing, setEditing] = useState<(typeof EMPTY & { id?: number }) | null>(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState('');

  const load = useCallback(() => {
    api.categories().then(setList).catch((e: any) => setMsg(e.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const save = async () => {
    if (!editing) return;
    if (!editing.name.trim()) { setMsg('请填写分类名'); return; }
    setMsg('');
    try {
      if (editing.id) await api.updateCategory(editing.id, editing);
      else await api.createCategory(editing);
      setEditing(null);
      load();
    } catch (e: any) {
      setMsg(e.detail || '保存失败');
    }
  };

  const remove = async (c: Category) => {
    if (!confirm(`删除分类「${c.name}」？若有闲置正在使用将无法删除。`)) return;
    try {
      await api.deleteCategory(c.id);
      load();
    } catch (e: any) {
      alert(e.detail || '删除失败');
    }
  };

  return (
    <div>
      <div className="page-title">分类管理</div>
      <div className="page-sub">闲置分类存数据库，可新增 / 改名 / 调估值基准 / 排序 / 启停。停用后发布时不可选。</div>

      <div className="row" style={{ marginBottom: 16 }}>
        <button onClick={() => setEditing({ ...EMPTY })}>＋ 新增分类</button>
        {msg && <span style={{ color: 'var(--red)' }}>{msg}</span>}
      </div>

      {editing && (
        <div className="card">
          <b style={{ marginRight: 16 }}>{editing.id ? '编辑分类' : '新增分类'}</b>
          <div className="row" style={{ flexWrap: 'wrap' }}>
            <input placeholder="分类名" value={editing.name}
                   onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            <input type="number" style={{ width: 90 }} min={1} max={15} value={editing.value_base}
                   title="AI 估值基准枚数"
                   onChange={(e) => setEditing({ ...editing, value_base: Number(e.target.value) || 0 })} />
            <input type="number" style={{ width: 80 }} value={editing.sort_order}
                   title="排序（越小越靠前）"
                   onChange={(e) => setEditing({ ...editing, sort_order: Number(e.target.value) || 0 })} />
            <input placeholder="说明(可选)" value={editing.note}
                   onChange={(e) => setEditing({ ...editing, note: e.target.value })} />
            <label className="row" style={{ gap: 6, whiteSpace: 'nowrap' }}>
              <input type="checkbox" checked={editing.is_active}
                     onChange={(e) => setEditing({ ...editing, is_active: e.target.checked })} />
              启用
            </label>
          </div>
          <div className="row mt">
            <button onClick={save}>保存</button>
            <button className="ghost" onClick={() => setEditing(null)}>取消</button>
          </div>
        </div>
      )}

      <table>
        <thead><tr><th>#</th><th>分类名</th><th>估值基准</th><th>排序</th><th>状态</th><th>说明</th><th>操作</th></tr></thead>
        <tbody>
          {list.map((c, i) => (
            <tr key={c.id}>
              <td>{i + 1}</td>
              <td><b>{c.name}</b></td>
              <td>{c.value_base} 枚</td>
              <td>{c.sort_order}</td>
              <td><span className={'chip ' + (c.is_active ? '' : 'gray')}>{c.is_active ? '启用' : '停用'}</span></td>
              <td style={{ color: 'var(--muted)' }}>{c.note}</td>
              <td>
                <button className="ghost" style={{ marginRight: 8 }}
                        onClick={() => setEditing({ id: c.id, name: c.name, value_base: c.value_base, note: c.note, sort_order: c.sort_order, is_active: c.is_active })}>
                  编辑
                </button>
                <button className="danger" onClick={() => remove(c)}>删除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!loading && list.length === 0 && <div className="empty">暂无分类，点「新增分类」添加</div>}
    </div>
  );
}