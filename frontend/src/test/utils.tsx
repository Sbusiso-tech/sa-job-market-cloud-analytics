import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { AppRoutes } from '../App';
import { createApiClient, type ApiClient } from '../api/client';
import { createMockFetch, type MockServerOptions } from '../api/mocks/server';
import { AuthProvider } from '../auth/AuthContext';
import { createMockAuth, MOCK_SESSION_KEY } from '../auth/mockAuth';
import { DEFAULT_CONFIG } from '../config';
import { ServicesProvider } from '../services';

export interface SetupOptions {
  route?: string;
  /** Email of a pre-signed-in mock user ("admin" in the email makes them an admin). */
  signedInAs?: string;
  server?: MockServerOptions;
  apiOverrides?: Partial<ApiClient>;
}

export function createTestServices(options: SetupOptions = {}) {
  if (options.signedInAs) window.sessionStorage.setItem(MOCK_SESSION_KEY, options.signedInAs);
  const auth = createMockAuth(window.sessionStorage);
  const fetch = createMockFetch({ latencyMs: [0, 0], ...options.server });
  const base = createApiClient({
    baseUrl: '/api',
    fetch,
    getIdToken: async () => (await auth.getSession())?.idToken ?? null,
  });
  const api: ApiClient = { ...base, ...options.apiOverrides };
  return { auth, api };
}

export function renderApp(options: SetupOptions = {}) {
  const { auth, api } = createTestServices(options);
  const user = userEvent.setup();
  const view = render(
    <ServicesProvider value={{ api, config: { ...DEFAULT_CONFIG, useMocks: true } }}>
      <AuthProvider service={auth}>
        <MemoryRouter initialEntries={[options.route ?? '/']}>
          <AppRoutes />
        </MemoryRouter>
      </AuthProvider>
    </ServicesProvider>,
  );
  return { ...view, api, auth, user };
}
