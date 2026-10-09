import { describe, expect, it, vi } from 'vitest';
import { makeUnsignedToken } from '../auth/tokens';
import { ApiError, createApiClient, type FetchFn } from './client';
import { createMockFetch } from './mocks/server';
import { MAX_ALERTS } from './types';

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function setup(response: Response | (() => Response), token: string | null = 'id.token.value') {
  const fetch = vi.fn<FetchFn>(async () => (typeof response === 'function' ? response() : response));
  const client = createApiClient({ baseUrl: '/api/', fetch, getIdToken: async () => token });
  return { client, fetch };
}

function headersOf(fetch: ReturnType<typeof vi.fn<FetchFn>>, call = 0): Record<string, string> {
  return (fetch.mock.calls[call]?.[1]?.headers ?? {}) as Record<string, string>;
}

describe('api client', () => {
  it('sends the ID token as a Bearer header on /me routes', async () => {
    const { client, fetch } = setup(jsonResponse(200, { items: [] }));
    await client.listSavedJobs();
    expect(fetch).toHaveBeenCalledWith('/api/me/saved-jobs', expect.objectContaining({ method: 'GET' }));
    expect(headersOf(fetch).Authorization).toBe('Bearer id.token.value');
  });

  it('sends the ID token on /admin routes', async () => {
    const { client, fetch } = setup(jsonResponse(202, { execution_id: 'manual-1', started_at: '2026-10-09T08:15:00Z' }));
    await client.startRun();
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/admin/runs');
    expect(headersOf(fetch).Authorization).toBe('Bearer id.token.value');
  });

  it('does not send a token to public routes', async () => {
    const { client, fetch } = setup(jsonResponse(200, { skills: [] }));
    await client.getSkillList();
    expect(headersOf(fetch).Authorization).toBeUndefined();
  });

  it('fails fast with unauthorized when signed out', async () => {
    const { client, fetch } = setup(jsonResponse(200, {}), null);
    await expect(client.listAlerts()).rejects.toMatchObject({ status: 401, code: 'unauthorized' });
    expect(fetch).not.toHaveBeenCalled();
  });

  it('builds query strings and skips empty parameters', async () => {
    const { client, fetch } = setup(jsonResponse(200, { items: [], next_cursor: null }));
    await client.listJobs({ province: 'KwaZulu-Natal', skill: undefined, limit: 20, cursor: 'eyJ+/=' });
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/public/jobs?province=KwaZulu-Natal&limit=20&cursor=eyJ%2B%2F%3D');
  });

  it('encodes path parameters', async () => {
    const { client, fetch } = setup(jsonResponse(200, {}));
    await client.getJob('a/b c');
    expect(fetch.mock.calls[0]?.[0]).toBe('/api/public/jobs/a%2Fb%20c');
  });

  it('sends JSON bodies', async () => {
    const { client, fetch } = setup(
      jsonResponse(201, { alert: { alert_id: 'a1', skills: ['Python'], created_at: 'x' }, subscription_status: 'pending_confirmation' }),
    );
    const res = await client.createAlert({ skills: ['Python'], province: 'Gauteng' });
    expect(res.subscription_status).toBe('pending_confirmation');
    const init = fetch.mock.calls[0]?.[1];
    expect(init?.method).toBe('POST');
    expect(init?.body).toBe('{"skills":["Python"],"province":"Gauteng"}');
    expect(headersOf(fetch)['Content-Type']).toBe('application/json');
  });

  it('parses the error shape into an ApiError', async () => {
    const { client } = setup(jsonResponse(409, { error: { code: 'limit_reached', message: 'You can have at most 5 alerts' } }));
    const err = await client.createAlert({ skills: ['SQL'] }).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 409, code: 'limit_reached', message: 'You can have at most 5 alerts' });
  });

  it("understands API Gateway's {message: 'Unauthorized'} body", async () => {
    const { client } = setup(jsonResponse(401, { message: 'Unauthorized' }));
    await expect(client.listAlerts()).rejects.toMatchObject({ status: 401, code: 'unauthorized', message: 'Unauthorized' });
  });

  it('copes with non-JSON error bodies', async () => {
    const { client } = setup(() => new Response('<html>Bad gateway</html>', { status: 502 }));
    await expect(client.getOverview()).rejects.toMatchObject({ status: 502, code: 'internal' });
  });

  it('returns undefined for 204 No Content', async () => {
    const { client } = setup(() => new Response(null, { status: 204 }));
    await expect(client.deleteAlert('a1')).resolves.toBeUndefined();
    await expect(client.deleteMe()).resolves.toBeUndefined();
  });

  it('turns fetch failures into a network_error', async () => {
    const fetch = vi.fn<FetchFn>(async () => {
      throw new TypeError('Failed to fetch');
    });
    const client = createApiClient({ baseUrl: '/api', fetch, getIdToken: async () => null });
    await expect(client.getOverview()).rejects.toMatchObject({ code: 'network_error' });
  });
});

describe('api client with the mock server', () => {
  const memberToken = makeUnsignedToken({ sub: 'member-1', email: 'member@example.com', exp: Date.now() / 1000 + 3600 });
  const adminToken = makeUnsignedToken({
    sub: 'admin-1',
    email: 'admin@example.com',
    'cognito:groups': ['admins'],
    exp: Date.now() / 1000 + 3600,
  });

  function mockClient(token: string | null) {
    return createApiClient({ baseUrl: '/api', fetch: createMockFetch({ latencyMs: [0, 0] }), getIdToken: async () => token });
  }

  it('serves realistic public data in the contract shape', async () => {
    const client = mockClient(null);
    const overview = await client.getOverview();
    expect(overview.total_jobs).toBeGreaterThan(0);
    expect(overview.seniority.length).toBeGreaterThan(0);
    const skills = await client.getSkills();
    expect(skills.skills[0]).toEqual(expect.objectContaining({ skill: 'SQL', change_vs_prev_week: expect.any(Number) }));
    const provinces = await client.getProvinces();
    expect(provinces.provinces[0]).toEqual(expect.objectContaining({ province: 'Gauteng', median_salary_zar: expect.any(Number) }));
    const trends = await client.getTrends();
    expect(trends.weeks).toHaveLength(8);
    expect((await client.getSalaries('python')).salaries).toHaveLength(1);
  });

  it('paginates ~40 jobs with next_cursor and filters by province and skill', async () => {
    const client = mockClient(null);
    const first = await client.listJobs({ limit: 20 });
    expect(first.items).toHaveLength(20);
    expect(first.next_cursor).toEqual(expect.any(String));
    const second = await client.listJobs({ limit: 20, cursor: first.next_cursor! });
    expect(second.items).toHaveLength(20);
    expect(second.next_cursor).toBeNull();
    const salaries = [...first.items, ...second.items].flatMap((j) => [j.salary_min_zar, j.salary_max_zar]).filter((v) => v !== null);
    expect(Math.min(...salaries)).toBeGreaterThanOrEqual(300_000);
    expect(Math.max(...salaries)).toBeLessThanOrEqual(1_400_000);

    const gauteng = await client.listJobs({ province: 'Gauteng', limit: 50 });
    expect(gauteng.items.length).toBeGreaterThan(0);
    expect(gauteng.items.every((j) => j.province === 'Gauteng')).toBe(true);
    const sql = await client.listJobs({ skill: 'sql', limit: 50 });
    expect(sql.items.every((j) => j.skills.includes('SQL'))).toBe(true);
    await expect(client.listJobs({ limit: 51 })).rejects.toMatchObject({ code: 'bad_request' });
    await expect(client.getJob('nope')).rejects.toMatchObject({ status: 404, code: 'not_found' });
  });

  it('rejects /me without a token using the API Gateway body', async () => {
    const fetch = createMockFetch({ latencyMs: [0, 0] });
    const res = await fetch('/api/me/alerts');
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ message: 'Unauthorized' });
  });

  it('keeps saved jobs in memory and saving is idempotent', async () => {
    const client = mockClient(memberToken);
    const { items } = await client.listJobs({ limit: 1 });
    const jobId = items[0]!.job_id;
    const saved = await client.saveJob(jobId);
    await client.saveJob(jobId);
    expect(saved).toEqual(expect.objectContaining({ job_id: jobId, title: items[0]!.title }));
    expect((await client.listSavedJobs()).items).toHaveLength(1);
    await client.unsaveJob(jobId);
    await client.unsaveJob(jobId);
    expect((await client.listSavedJobs()).items).toHaveLength(0);
    await expect(client.saveJob('missing')).rejects.toMatchObject({ code: 'not_found' });
  });

  it('validates alerts and enforces the max-5 rule with limit_reached', async () => {
    const client = mockClient(memberToken);
    expect((await client.listAlerts()).subscription_status).toBe('none');
    await expect(client.createAlert({ skills: [] })).rejects.toMatchObject({ code: 'bad_request' });
    await expect(client.createAlert({ skills: ['Cobol++'] })).rejects.toMatchObject({ code: 'bad_request' });
    await expect(client.createAlert({ skills: ['a', 'b', 'c', 'd', 'e', 'f'] })).rejects.toMatchObject({ code: 'bad_request' });

    const first = await client.createAlert({ skills: ['python', 'AWS'], province: 'Gauteng' });
    expect(first.alert.skills).toEqual(['Python', 'AWS']);
    expect(first.subscription_status).toBe('pending_confirmation');
    for (let i = 1; i < MAX_ALERTS; i++) await client.createAlert({ skills: ['SQL'] });
    await expect(client.createAlert({ skills: ['SQL'] })).rejects.toMatchObject({ status: 409, code: 'limit_reached' });

    const { alerts } = await client.listAlerts();
    for (const a of alerts) await client.deleteAlert(a.alert_id);
    expect((await client.listAlerts()).subscription_status).toBe('none');
  });

  it('restricts admin routes to the admins group', async () => {
    await expect(mockClient(memberToken).listRuns()).rejects.toMatchObject({ status: 403, code: 'forbidden' });
    const admin = mockClient(adminToken);
    const started = await admin.startRun();
    const runs = await admin.listRuns();
    expect(runs.runs[0]).toEqual(expect.objectContaining({ execution_id: started.execution_id, status: 'RUNNING', fetched: null }));
    expect(runs.dlq_depth).toBe(0);
  });

  it('deletes all user data on DELETE /me', async () => {
    const client = mockClient(memberToken);
    await client.createAlert({ skills: ['Excel'] });
    await client.deleteMe();
    expect((await client.listAlerts()).alerts).toEqual([]);
  });
});
