import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Loading } from '../components/StatusViews';
import { useAuth } from './AuthContext';

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <Loading label="Checking your session…" />;
  if (status === 'signedOut') return <Navigate to="/signin" replace state={{ from: location.pathname + location.search }} />;
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === 'loading') return <Loading label="Checking your session…" />;
  if (status === 'signedOut') return <Navigate to="/signin" replace state={{ from: location.pathname }} />;
  if (!user?.isAdmin) return <Navigate to="/" replace state={{ notice: 'The admin area is only for administrators.' }} />;
  return <>{children}</>;
}
