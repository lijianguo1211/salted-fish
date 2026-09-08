import { useEffect, useMemo, useState } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { Layout, Menu, Button, Typography, Spin, theme, Grid } from 'antd';
import {
  AlertOutlined,
  AppstoreOutlined,
  ClusterOutlined,
  LogoutOutlined,
  RobotOutlined,
  ShoppingOutlined,
  TeamOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons';
import { api } from './api';
import { clearAuth, getStoredAdmin, getToken } from './api/client';
import Login from './pages/Login';
import Categories from './pages/Categories';
import Reports from './pages/Reports';
import Items from './pages/Items';
import Users from './pages/Users';
import Orgs from './pages/Orgs';
import Llms from './pages/Llms';

const { Header, Sider, Content } = Layout;
const { useBreakpoint } = Grid;

const MENU = [
  { key: '/reports', icon: <AlertOutlined />, label: '举报处理' },
  { key: '/items', icon: <ShoppingOutlined />, label: '物品管理' },
  { key: '/categories', icon: <AppstoreOutlined />, label: '分类管理' },
  { key: '/users', icon: <TeamOutlined />, label: '孩子/积分' },
  { key: '/orgs', icon: <ClusterOutlined />, label: '组织审核' },
  { key: '/llms', icon: <RobotOutlined />, label: '大模型' },
];

function AdminLayout({ admin, onLogout }: { admin: any; onLogout: () => void }) {
  const navigate = useNavigate();
  const location = useLocation();
  const screens = useBreakpoint();
  const isMobile = !screens.md;
  const [collapsed, setCollapsed] = useState(false);
  const { token } = theme.useToken();

  useEffect(() => {
    if (isMobile) setCollapsed(true);
  }, [isMobile]);

  const selected = useMemo(() => {
    const hit = MENU.find((m) => location.pathname.startsWith(m.key));
    return [hit?.key || '/reports'];
  }, [location.pathname]);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        breakpoint="md"
        collapsedWidth={isMobile ? 0 : 64}
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        width={220}
        style={{
          background: '#fff',
          borderRight: `1px solid ${token.colorBorderSecondary}`,
        }}
      >
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 20px',
            fontWeight: 800,
            fontSize: 18,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
          }}
        >
          {collapsed ? '🐟' : <>🥇 咸鱼<span style={{ color: token.colorPrimary }}>市场</span></>}
        </div>
        <Menu
          mode="inline"
          selectedKeys={selected}
          items={MENU}
          onClick={({ key }) => {
            navigate(key);
            if (isMobile) setCollapsed(true);
          }}
          style={{ borderInlineEnd: 'none' }}
        />
      </Sider>

      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
            position: 'sticky',
            top: 0,
            zIndex: 10,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed((v) => !v)}
          />
          <Typography.Text type="secondary" style={{ flex: 1 }}>
            管理后台
          </Typography.Text>
          <Typography.Text strong>{admin?.name || admin?.email || '管理员'}</Typography.Text>
          <Button icon={<LogoutOutlined />} onClick={onLogout}>
            退出
          </Button>
        </Header>

        <Content className="admin-content" style={{ padding: isMobile ? 12 : 24 }}>
          <Routes>
            <Route path="/reports" element={<Reports />} />
            <Route path="/items" element={<Items />} />
            <Route path="/categories" element={<Categories />} />
            <Route path="/users" element={<Users />} />
            <Route path="/orgs" element={<Orgs />} />
            <Route path="/llms" element={<Llms />} />
            <Route path="*" element={<Navigate to="/reports" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
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
    api.me().then(() => setAuthed(true)).catch(() => {
      clearAuth();
      setAuthed(false);
    });
  }, [location.pathname]);

  if (authed === null) {
    return (
      <div className="login-page">
        <Spin size="large" tip="加载中..." />
      </div>
    );
  }

  if (!authed) return <Login onAuth={() => setAuthed(true)} />;

  return (
    <AdminLayout
      admin={getStoredAdmin()}
      onLogout={() => {
        clearAuth();
        setAuthed(false);
      }}
    />
  );
}
