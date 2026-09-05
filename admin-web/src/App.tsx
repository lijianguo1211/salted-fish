import { useEffect, useState } from 'react';
import { Navigate, Route, Routes, NavLink, useLocation } from 'react-router-dom';
import { api } from './api';
import { clearAuth, getStoredAdmin, getToken } from './api/client';
import Login from './pages/Login';
import Categories from './pages/Categories';
import Reports from './pages/Reports';
import Items from './pages/Items';
import Users from './pages/Users';
import Orgs from './pages/Orgs';
import Llms from './pages/Llms';

function Layout({ admin, onLogout }: { admin: any; onLogout: () => void }) {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">🥇 咸鱼<b>市场</b></div>
        <nav>
          <NavLink to="/reports" className={({ isActive }) => (isActive ? 'active' : '')}>举报处理</NavLink>
          <NavLink to="/items" className={({ isActive }) => (isActive ? 'active' : '')}>物品管理</NavLink>
          <NavLink to="/categories" className={({ isActive }) => (isActive ? 'active' : '')}>分类管理</NavLink>
          <NavLink to="/users" className={({ isActive }) => (isActive ? 'active' : '')}>孩子/积分</NavLink>
          <NavLink to="/orgs" className={({ isActive }) => (isActive ? 'active' : '')}>组织审核</NavLink>
          <NavLink to="/llms" className={({ isActive }) => (isActive ? 'active' : '')}>大模型</NavLink>
        </nav>
        <div style={{ marginTop: 'auto', paddingTop: 20, fontSize: 13, color: 'var(--muted)' }}>
          <div className="row"><b className="grow">👤 {admin?.name || '管理员'}</b></div>
          <button className="ghost" style={{ marginTop: 10, width: '100%' }} onClick={onLogout}>退出登录</button>
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/reports" element={<Reports />} />
          <Route path="/items" element={<Items />} />
          <Route path="/categories" element={<Categories />} />
          <Route path="/users" element={<Users />} />
          <Route path="/orgs" element={<Orgs />} />
          <Route path="/llms" element={<Llms />} />
          <Route path="*" element={<Navigate to="/reports" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const location = useLocation();

  useEffect(() => {
    if (!getToken()) {
      setAuthed(false);
      return;
    }
    // 有 token，向后端确认有效性
    api.me().then(() => setAuthed(true)).catch(() => {
      clearAuth();
      setAuthed(false);
    });
  }, [location.pathname]);

  if (authed === null) return <div className="login-wrap"><div className="card"><div className="empty">加载中...</div></div></div>;

  if (!authed) return <Login onAuth={() => setAuthed(true)} />;

  return <Layout admin={getStoredAdmin()} onLogout={() => { clearAuth(); setAuthed(false); }} />;
}