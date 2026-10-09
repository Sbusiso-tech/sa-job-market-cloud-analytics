import type { FetchFn } from '../client';
import {
  MAX_ALERT_SKILLS,
  MAX_ALERTS,
  PROVINCES,
  type Alert,
  type ErrorCode,
  type Job,
  type PipelineRun,
  type Province,
  type SavedJob,
  type SubscriptionStatus,
} from '../types';
import { ADMIN_GROUP, groupsFromClaims, isExpired, parseJwtClaims } from '../../auth/tokens';
import { buildDataset, SKILL_LIST, type MockDataset } from './data';

export interface MockServerOptions {
  baseUrl?: string;
  /** Artificial latency range in ms; [0, 0] in tests. */
  latencyMs?: [number, number];
  dataset?: MockDataset;
  /** How long a fake SNS subscription stays pending before it becomes confirmed. */
  confirmAfterMs?: number;
  /** How long a manual pipeline run stays RUNNING. */
  runDurationMs?: number;
  now?: () => number;
}

interface Caller {
  sub: string;
  email: string;
  isAdmin: boolean;
}

interface UserState {
  email: string;
  saved: Map<string, SavedJob>;
  alerts: Alert[];
  subscribedAt: number | null;
}

class HttpError extends Error {
  readonly status: number;
  readonly code: ErrorCode;
  constructor(status: number, code: ErrorCode, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function noContent(): Response {
  return new Response(null, { status: 204 });
}

function isoNow(now: number): string {
  return new Date(now).toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function encodeCursor(offset: number): string {
  return btoa(JSON.stringify({ o: offset }));
}

function decodeCursor(cursor: string): number {
  try {
    const parsed: unknown = JSON.parse(atob(cursor));
    const offset = (parsed as { o?: unknown }).o;
    if (typeof offset === 'number' && offset >= 0) return offset;
  } catch {
    // fall through
  }
  throw new HttpError(400, 'bad_request', 'Invalid cursor');
}

const SKILL_BY_LOWER = new Map(SKILL_LIST.map((s) => [s.name.toLowerCase(), s.name]));

function isProvince(value: unknown): value is Province {
  return typeof value === 'string' && (PROVINCES as readonly string[]).includes(value);
}

export function createMockFetch(options: MockServerOptions = {}): FetchFn {
  const baseUrl = (options.baseUrl ?? '/api').replace(/\/+$/, '');
  const [minLatency, maxLatency] = options.latencyMs ?? [150, 450];
  const now = options.now ?? (() => Date.now());
  const confirmAfterMs = options.confirmAfterMs ?? 45_000;
  const runDurationMs = options.runDurationMs ?? 20_000;
  const data = options.dataset ?? buildDataset(now());
  const users = new Map<string, UserState>();
  const runs: PipelineRun[] = [...data.runs];
  let alertSeq = 0;

  const jobsById = new Map<string, Job>(data.jobs.map((j) => [j.job_id, j]));

  function userState(caller: Caller): UserState {
    let state = users.get(caller.sub);
    if (!state) {
      state = { email: caller.email, saved: new Map(), alerts: [], subscribedAt: null };
      users.set(caller.sub, state);
    }
    return state;
  }

  function subscriptionStatus(state: UserState): SubscriptionStatus {
    if (state.subscribedAt === null) return 'none';
    return now() - state.subscribedAt >= confirmAfterMs ? 'confirmed' : 'pending_confirmation';
  }

  function authenticate(headers: Headers): Caller {
    const header = headers.get('Authorization') ?? '';
    const match = /^Bearer (.+)$/.exec(header);
    const claims = match?.[1] ? parseJwtClaims(match[1]) : null;
    if (!claims || isExpired(claims, now(), 0)) {
      // API Gateway's JWT authorizer answers with its own body shape.
      throw Object.assign(new HttpError(401, 'unauthorized', 'Unauthorized'), { gateway: true });
    }
    return {
      sub: claims.sub,
      email: typeof claims.email === 'string' ? claims.email : '',
      isAdmin: groupsFromClaims(claims).includes(ADMIN_GROUP),
    };
  }

  function settleRuns() {
    for (const [i, run] of runs.entries()) {
      if (run.status === 'RUNNING' && now() - Date.parse(run.started_at) >= runDurationMs) {
        runs[i] = {
          ...run,
          status: 'SUCCEEDED',
          stopped_at: isoNow(Date.parse(run.started_at) + runDurationMs),
          fetched: 360,
          new_jobs: 42,
          failed: 0,
        };
      }
    }
  }

  function listJobs(params: URLSearchParams): Response {
    const limitRaw = params.get('limit');
    const limit = limitRaw === null ? 20 : Number(limitRaw);
    if (!Number.isInteger(limit) || limit < 1 || limit > 50) {
      throw new HttpError(400, 'bad_request', 'limit must be an integer from 1 to 50');
    }
    const provinceRaw = params.get('province');
    const province = provinceRaw ? PROVINCES.find((p) => p.toLowerCase() === provinceRaw.trim().toLowerCase()) : null;
    if (provinceRaw && !province) throw new HttpError(400, 'bad_request', 'Unknown province');
    const skill = params.get('skill')?.toLowerCase();
    const cursor = params.get('cursor');
    const offset = cursor ? decodeCursor(cursor) : 0;

    const filtered = data.jobs.filter(
      (j) =>
        (!province || j.province === province) &&
        (!skill || j.skills.some((s) => s.toLowerCase() === skill)),
    );
    const items = filtered.slice(offset, offset + limit);
    const next = offset + limit < filtered.length ? encodeCursor(offset + limit) : null;
    return json(200, { items, next_cursor: next });
  }

  function createAlert(caller: Caller, body: unknown): Response {
    const state = userState(caller);
    if (typeof body !== 'object' || body === null) throw new HttpError(400, 'bad_request', 'Body must be a JSON object');
    const { skills, province } = body as { skills?: unknown; province?: unknown };
    if (!Array.isArray(skills) || skills.length < 1 || skills.length > MAX_ALERT_SKILLS) {
      throw new HttpError(400, 'bad_request', `Choose between 1 and ${MAX_ALERT_SKILLS} skills`);
    }
    const normalised: string[] = [];
    for (const raw of skills) {
      const name = typeof raw === 'string' ? SKILL_BY_LOWER.get(raw.trim().toLowerCase()) : undefined;
      if (!name) throw new HttpError(400, 'bad_request', `Unknown skill: ${String(raw)}`);
      if (!normalised.includes(name)) normalised.push(name);
    }
    if (province !== undefined && province !== null && !isProvince(province)) {
      throw new HttpError(400, 'bad_request', 'Unknown province');
    }
    if (state.alerts.length >= MAX_ALERTS) {
      throw new HttpError(409, 'limit_reached', `You can have at most ${MAX_ALERTS} alerts`);
    }
    alertSeq += 1;
    const alert: Alert = {
      alert_id: `alert-${alertSeq.toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`,
      skills: normalised,
      province: isProvince(province) ? province : null,
      created_at: isoNow(now()),
    };
    state.alerts.push(alert);
    if (state.subscribedAt === null) state.subscribedAt = now();
    return json(201, { alert, subscription_status: subscriptionStatus(state) });
  }

  async function route(method: string, path: string, params: URLSearchParams, headers: Headers, rawBody: string | null): Promise<Response> {
    const segments = path.split('/').filter(Boolean).map(decodeURIComponent);
    const [area, resource, id] = segments;

    if (area === 'public' && method === 'GET') {
      const updated = data.overview.last_updated;
      switch (resource) {
        case 'overview':
          if (!id) return json(200, data.overview);
          break;
        case 'skills':
          if (!id) return json(200, { last_updated: updated, skills: data.skills });
          break;
        case 'skill-list':
          if (!id) return json(200, { skills: SKILL_LIST });
          break;
        case 'salaries': {
          const skill = params.get('skill')?.toLowerCase();
          const salaries = skill ? data.salaries.filter((s) => s.skill.toLowerCase() === skill) : data.salaries;
          return json(200, { last_updated: updated, salaries });
        }
        case 'provinces':
          return json(200, { last_updated: updated, provinces: data.provinces });
        case 'skill-pairs':
          return json(200, { last_updated: updated, pairs: data.pairs });
        case 'trends':
          return json(200, { last_updated: updated, weeks: data.trends });
        case 'jobs': {
          if (!id) return listJobs(params);
          const job = jobsById.get(id);
          if (!job) throw new HttpError(404, 'not_found', 'Job not found');
          return json(200, job);
        }
      }
    }

    if (area === 'me') {
      const caller = authenticate(headers);
      const state = userState(caller);
      if (!resource && method === 'DELETE') {
        users.delete(caller.sub);
        return noContent();
      }
      if (resource === 'saved-jobs') {
        if (!id && method === 'GET') {
          const items = [...state.saved.values()].sort((a, b) => b.saved_at.localeCompare(a.saved_at));
          return json(200, { items });
        }
        if (id && method === 'PUT') {
          const existing = state.saved.get(id);
          if (existing) return json(200, existing);
          const job = jobsById.get(id);
          if (!job) throw new HttpError(404, 'not_found', 'Job not found');
          const item: SavedJob = {
            job_id: job.job_id,
            title: job.title,
            company: job.company,
            province: job.province,
            saved_at: isoNow(now()),
          };
          state.saved.set(id, item);
          return json(200, item);
        }
        if (id && method === 'DELETE') {
          state.saved.delete(id);
          return noContent();
        }
      }
      if (resource === 'alerts') {
        if (!id && method === 'GET') {
          return json(200, {
            email: state.email,
            subscription_status: subscriptionStatus(state),
            alerts: state.alerts,
          });
        }
        if (!id && method === 'POST') {
          let body: unknown;
          try {
            body = rawBody ? JSON.parse(rawBody) : null;
          } catch {
            throw new HttpError(400, 'bad_request', 'Body must be valid JSON');
          }
          return createAlert(caller, body);
        }
        if (id && method === 'DELETE') {
          state.alerts = state.alerts.filter((a) => a.alert_id !== id);
          if (state.alerts.length === 0) state.subscribedAt = null;
          return noContent();
        }
      }
    }

    if (area === 'admin') {
      const caller = authenticate(headers);
      if (!caller.isAdmin) throw new HttpError(403, 'forbidden', 'Admins only');
      if (resource === 'runs' && !id) {
        if (method === 'GET') {
          settleRuns();
          return json(200, { dlq_depth: 0, runs: runs.slice(0, 20) });
        }
        if (method === 'POST') {
          const startedAt = isoNow(now());
          const executionId = `manual-${startedAt.replace(/[-:]/g, '')}`;
          runs.unshift({
            execution_id: executionId,
            status: 'RUNNING',
            started_at: startedAt,
            stopped_at: null,
            fetched: null,
            new_jobs: null,
            failed: null,
          });
          return json(202, { execution_id: executionId, started_at: startedAt });
        }
      }
    }

    throw new HttpError(404, 'not_found', 'Route not found');
  }

  return async (input, init = {}) => {
    const delay = minLatency + Math.random() * (maxLatency - minLatency);
    if (delay > 0) await new Promise((resolve) => setTimeout(resolve, delay));

    const url = new URL(input, 'http://mock.local');
    const prefix = new URL(baseUrl || '/', 'http://mock.local').pathname.replace(/\/+$/, '');
    if (!url.pathname.startsWith(`${prefix}/`)) return json(404, { error: { code: 'not_found', message: 'Not found' } });
    const path = url.pathname.slice(prefix.length);
    const method = (init.method ?? 'GET').toUpperCase();
    const headers = new Headers(init.headers);
    const body = typeof init.body === 'string' ? init.body : null;

    try {
      return await route(method, path, url.searchParams, headers, body);
    } catch (err) {
      if (err instanceof HttpError) {
        if ((err as HttpError & { gateway?: boolean }).gateway) return json(401, { message: 'Unauthorized' });
        return json(err.status, { error: { code: err.code, message: err.message } });
      }
      return json(500, { error: { code: 'internal', message: 'Internal error' } });
    }
  };
}
