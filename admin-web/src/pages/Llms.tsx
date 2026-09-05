import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';

type Vendor = { vendor: string; label: string; base_url: string; model: string };
type Llm = {
  id: number;
  name: string;
  vendor: string;
  base_url: string;
  api_key: string;
  api_key_set: boolean;
  model: string;
  is_active: boolean;
  sort_order: number;
  timeout_sec: number;
  note: string;
  last_error: string;
  last_ok_at: string;
  fail_count: number;
};

const EMPTY = {
  name: '',
  vendor: 'siliconflow',
  base_url: 'https://api.siliconflow.cn/v1',
  api_key: '',
  model: 'Qwen/Qwen2.5-VL-72B-Instruct',
  is_active: true,
  sort_order: 0,
  timeout_sec: 30,
  note: '',
};

export default function Llms() {
  const [list, setList] = useState<Llm[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [editing, setEditing] = useState<(typeof EMPTY & { id?: number }) | null>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    Promise.all([api.llmProviders(), api.llmVendors()])
      .then(([rows, vs]) => {
        setList(rows || []);
        setVendors(vs || []);
      })
      .catch((e: any) => setMsg(e.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  const applyVendor = (vendor: string, cur: typeof EMPTY & { id?: number }) => {
    const preset = vendors.find((v) => v.vendor === vendor);
    if (!preset) return { ...cur, vendor };
    return {
      ...cur,
      vendor,
      base_url: preset.base_url,
      model: preset.model,
      name: cur.name || `${preset.label}-免费`,
    };
  };

  const save = async () => {
    if (!editing) return;
    if (!editing.name.trim()) { setMsg('请填写显示名'); return; }
    if (!editing.base_url.trim()) { setMsg('请填写 Base URL'); return; }
    if (!editing.id && !editing.api_key.trim()) { setMsg('新增时必须填 API Key'); return; }
    setMsg('');
    try {
      const body = { ...editing };
      if (editing.id && !editing.api_key.trim()) {
        // 编辑时留空 = 不改 key
        delete (body as any).api_key;
      }
      if (editing.id) await api.updateLlm(editing.id, body);
      else await api.createLlm(body);
      setEditing(null);
      load();
    } catch (e: any) {
      setMsg(e.detail || '保存失败');
    }
  };

  const remove = async (row: Llm) => {
    if (!confirm(`删除「${row.name}」？`)) return;
    try {
      await api.deleteLlm(row.id);
      load();
    } catch (e: any) {
      alert(e.detail || '删除失败');
    }
  };

  const test = async (row: Llm) => {
    try {
      const r = await api.testLlm(row.id);
      alert(`连通正常：${r.reply || 'ok'}`);
      load();
    } catch (e: any) {
      alert(e.detail || '连通失败');
      load();
    }
  };

  return (
    <div>
      <div className="page-title">大模型管理</div>
      <div className="page-sub">
        配置多个免费 / 公益 API Key（OpenAI 兼容）。估值时按优先级依次尝试，某一家失败自动切下一家；全部失败回退规则引擎。
      </div>

      <div className="row" style={{ marginBottom: 16 }}>
        <button onClick={() => setEditing({ ...EMPTY })}>＋ 新增配置</button>
        {msg && <span style={{ color: 'var(--red)' }}>{msg}</span>}
      </div>

      {editing && (
        <div className="card">
          <b>{editing.id ? '编辑配置' : '新增配置'}</b>
          <div className="row mt" style={{ flexWrap: 'wrap', gap: 10 }}>
            <select
              value={editing.vendor}
              onChange={(e) => setEditing(applyVendor(e.target.value, editing))}
              title="厂商"
            >
              {vendors.map((v) => (
                <option key={v.vendor} value={v.vendor}>{v.label}</option>
              ))}
            </select>
            <input placeholder="显示名" value={editing.name}
                   onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            <input placeholder="Base URL" style={{ minWidth: 260 }} value={editing.base_url}
                   onChange={(e) => setEditing({ ...editing, base_url: e.target.value })} />
            <input placeholder={editing.id ? 'API Key（留空不改）' : 'API Key'} style={{ minWidth: 220 }}
                   value={editing.api_key}
                   onChange={(e) => setEditing({ ...editing, api_key: e.target.value })} />
            <input placeholder="模型名" value={editing.model}
                   onChange={(e) => setEditing({ ...editing, model: e.target.value })} />
            <input type="number" style={{ width: 80 }} title="优先级，越小越先"
                   value={editing.sort_order}
                   onChange={(e) => setEditing({ ...editing, sort_order: Number(e.target.value) || 0 })} />
            <input type="number" style={{ width: 90 }} title="超时秒"
                   value={editing.timeout_sec}
                   onChange={(e) => setEditing({ ...editing, timeout_sec: Number(e.target.value) || 30 })} />
            <input placeholder="备注" value={editing.note}
                   onChange={(e) => setEditing({ ...editing, note: e.target.value })} />
            <label className="row" style={{ gap: 6 }}>
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
        <thead>
          <tr>
            <th>优先</th><th>名称</th><th>厂商</th><th>模型</th><th>Key</th>
            <th>状态</th><th>最近成功</th><th>失败</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          {list.map((row) => (
            <tr key={row.id}>
              <td>{row.sort_order}</td>
              <td>
                <b>{row.name}</b>
                <div style={{ color: 'var(--muted)', fontSize: 12 }}>{row.base_url}</div>
                {row.last_error && <div style={{ color: 'var(--red)', fontSize: 12 }}>{row.last_error}</div>}
              </td>
              <td>{row.vendor}</td>
              <td>{row.model}</td>
              <td style={{ fontFamily: 'monospace' }}>{row.api_key || '—'}</td>
              <td><span className={'chip ' + (row.is_active ? '' : 'gray')}>{row.is_active ? '启用' : '停用'}</span></td>
              <td style={{ color: 'var(--muted)', fontSize: 13 }}>{row.last_ok_at || '—'}</td>
              <td>{row.fail_count || 0}</td>
              <td>
                <button className="ghost" style={{ marginRight: 6 }} onClick={() => test(row)}>测试</button>
                <button className="ghost" style={{ marginRight: 6 }}
                        onClick={() => setEditing({
                          id: row.id,
                          name: row.name,
                          vendor: row.vendor,
                          base_url: row.base_url,
                          api_key: '',
                          model: row.model,
                          is_active: row.is_active,
                          sort_order: row.sort_order,
                          timeout_sec: row.timeout_sec,
                          note: row.note,
                        })}>编辑</button>
                <button className="danger" onClick={() => remove(row)}>删除</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!loading && list.length === 0 && (
        <div className="empty">暂无配置。可先加硅基流动 / Groq 等免费额度 Key，估值时会自动轮询。</div>
      )}
    </div>
  );
}
