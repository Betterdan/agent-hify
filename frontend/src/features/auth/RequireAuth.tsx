import { Navigate, Outlet } from 'react-router-dom';

import { getToken } from '@/lib/auth/token';

export function RequireAuth() {
  return getToken() ? <Outlet /> : <Navigate to="/login" replace />;
}
