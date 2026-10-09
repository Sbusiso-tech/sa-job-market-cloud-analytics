import { describe, expect, it, vi } from 'vitest';
import { DEFAULT_CONFIG, loadConfig } from './config';

function stubFetch(routes: Record<string, () => Response>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => (routes[url] ?? (() => new Response('not found', { status: 404 })))()),
  );
}

describe('loadConfig', () => {
  it('uses /config.json when it exists', async () => {
    stubFetch({
      '/config.json': () =>
        new Response(
          JSON.stringify({ apiBaseUrl: '/api', region: 'eu-west-1', userPoolId: 'eu-west-1_abc', userPoolClientId: 'client', useMocks: false }),
        ),
    });
    await expect(loadConfig()).resolves.toEqual({
      apiBaseUrl: '/api',
      region: 'eu-west-1',
      userPoolId: 'eu-west-1_abc',
      userPoolClientId: 'client',
      useMocks: false,
    });
    vi.unstubAllGlobals();
  });

  it('falls back to config.example.json when the dev server answers with index.html', async () => {
    stubFetch({
      '/config.json': () => new Response('<!doctype html><html></html>', { status: 200 }),
      '/config.example.json': () => new Response(JSON.stringify({ ...DEFAULT_CONFIG, region: 'af-south-1' })),
    });
    await expect(loadConfig()).resolves.toMatchObject({ useMocks: true, region: 'af-south-1' });
    vi.unstubAllGlobals();
  });

  it('falls back to built-in defaults when nothing loads', async () => {
    stubFetch({});
    await expect(loadConfig()).resolves.toEqual(DEFAULT_CONFIG);
    vi.unstubAllGlobals();
  });
});
