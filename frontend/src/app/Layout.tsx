import { Layout as AntLayout, Menu } from 'antd';
import { Link, Outlet, useLocation } from 'react-router-dom';

const items = [
  { key: '/models', label: <Link to="/models">模型</Link> },
  { key: '/apps', label: <Link to="/apps">应用</Link> },
  { key: '/knowledge', label: <Link to="/knowledge">知识库</Link> },
  { key: '/observability', label: <Link to="/observability">用量 / Trace</Link> },
];

export function Layout() {
  const { pathname } = useLocation();
  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <AntLayout.Header>
        <Menu theme="dark" mode="horizontal" selectedKeys={[pathname]} items={items} />
      </AntLayout.Header>
      <AntLayout.Content style={{ padding: 24 }}>
        <Outlet />
      </AntLayout.Content>
    </AntLayout>
  );
}
