import './polyfills';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { createApiClient, type FetchFn } from './api/client';
import { AuthProvider } from './auth/AuthContext';
import type { AuthService } from './auth/service';
import { loadConfig } from './config';
import { ServicesProvider } from './services';
import './styles.css';

async function bootstrap() {
  const config = await loadConfig();

  let auth: AuthService;
  let fetchImpl: FetchFn | undefined;
  if (config.useMocks) {
    const [{ createMockAuth }, { createMockFetch }] = await Promise.all([
      import('./auth/mockAuth'),
      import('./api/mocks/server'),
    ]);
    auth = createMockAuth();
    fetchImpl = createMockFetch({ baseUrl: config.apiBaseUrl });
  } else {
    const { createCognitoAuth } = await import('./auth/cognitoAuth');
    auth = createCognitoAuth(config);
  }

  const api = createApiClient({
    baseUrl: config.apiBaseUrl,
    fetch: fetchImpl,
    getIdToken: async () => (await auth.getSession())?.idToken ?? null,
  });

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ServicesProvider value={{ api, config }}>
        <AuthProvider service={auth}>
          <App />
        </AuthProvider>
      </ServicesProvider>
    </StrictMode>,
  );
}

void bootstrap();
