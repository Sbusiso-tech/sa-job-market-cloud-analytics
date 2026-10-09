import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { AuthService } from './service';
import type { AuthUser } from './tokens';

export type AuthStatus = 'loading' | 'signedIn' | 'signedOut';

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  service: AuthService;
  signIn(email: string, password: string): Promise<AuthUser>;
  signOut(): Promise<void>;
  /** Deletes the Cognito user (after the API data is gone) and clears local state. */
  deleteUser(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ service, children }: { service: AuthService; children: ReactNode }) {
  const [state, setState] = useState<{ status: AuthStatus; user: AuthUser | null }>({
    status: 'loading',
    user: null,
  });

  useEffect(() => {
    let active = true;
    service
      .getSession()
      .then((session) => {
        if (active) setState(session ? { status: 'signedIn', user: session.user } : { status: 'signedOut', user: null });
      })
      .catch(() => {
        if (active) setState({ status: 'signedOut', user: null });
      });
    return () => {
      active = false;
    };
  }, [service]);

  const signIn = useCallback(
    async (email: string, password: string) => {
      const session = await service.signIn(email, password);
      setState({ status: 'signedIn', user: session.user });
      return session.user;
    },
    [service],
  );

  const signOut = useCallback(async () => {
    await service.signOut();
    setState({ status: 'signedOut', user: null });
  }, [service]);

  const deleteUser = useCallback(async () => {
    await service.deleteUser();
    await service.signOut();
    setState({ status: 'signedOut', user: null });
  }, [service]);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, service, signIn, signOut, deleteUser }),
    [state, service, signIn, signOut, deleteUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
