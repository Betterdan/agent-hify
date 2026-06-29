import { createBrowserRouter, Navigate } from 'react-router-dom';

import { Layout } from '@/app/Layout';
import { RequireAuth } from '@/features/auth/RequireAuth';
import { LoginPage } from '@/features/auth/LoginPage';
import { ModelsPage } from '@/features/models/ModelsPage';
import { ObservabilityPage } from '@/features/observability/ObservabilityPage';
import { AppsPage } from '@/features/apps/AppsPage';
import { ChatPage } from '@/features/chat/ChatPage';
import { AgentPage } from '@/features/agent/AgentPage';
import { KnowledgePage } from '@/features/knowledge/KnowledgePage';
import { ToolsPage } from '@/features/tools/ToolsPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: '/', element: <Navigate to="/models" replace /> },
          { path: '/models', element: <ModelsPage /> },
          { path: '/apps', element: <AppsPage /> },
          { path: '/apps/:appId/chat', element: <ChatPage /> },
          { path: '/apps/:appId/run', element: <AgentPage /> },
          { path: '/knowledge', element: <KnowledgePage /> },
          { path: '/tools', element: <ToolsPage /> },
          { path: '/observability', element: <ObservabilityPage /> },
        ],
      },
    ],
  },
]);
