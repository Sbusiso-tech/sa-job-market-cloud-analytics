export interface AppConfig {
  apiBaseUrl: string;
  region: string;
  userPoolId: string;
  userPoolClientId: string;
  useMocks: boolean;
}

export const DEFAULT_CONFIG: AppConfig = {
  apiBaseUrl: '/api',
  region: 'eu-west-1',
  userPoolId: '',
  userPoolClientId: '',
  useMocks: true,
};

function normalise(raw: unknown): AppConfig | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const r = raw as Partial<Record<keyof AppConfig, unknown>>;
  return {
    apiBaseUrl: typeof r.apiBaseUrl === 'string' && r.apiBaseUrl ? r.apiBaseUrl : DEFAULT_CONFIG.apiBaseUrl,
    region: typeof r.region === 'string' && r.region ? r.region : DEFAULT_CONFIG.region,
    userPoolId: typeof r.userPoolId === 'string' ? r.userPoolId : '',
    userPoolClientId: typeof r.userPoolClientId === 'string' ? r.userPoolClientId : '',
    useMocks: r.useMocks === true,
  };
}

async function tryLoad(url: string): Promise<AppConfig | null> {
  try {
    const res = await fetch(url, { cache: 'no-store', headers: { Accept: 'application/json' } });
    if (!res.ok) return null;
    // The dev server answers unknown paths with index.html, so parse defensively.
    return normalise(JSON.parse(await res.text()));
  } catch {
    return null;
  }
}

/** Loads /config.json (written at deploy time), falling back to the shipped example in dev. */
export async function loadConfig(): Promise<AppConfig> {
  return (await tryLoad('/config.json')) ?? (await tryLoad('/config.example.json')) ?? DEFAULT_CONFIG;
}
