import type {
  AlertsResponse,
  CreateAlertRequest,
  CreateAlertResponse,
  ErrorCode,
  Job,
  JobsPage,
  JobsQuery,
  Overview,
  ProvincesResponse,
  RunsResponse,
  SalariesResponse,
  SavedJob,
  SavedJobsResponse,
  SkillListResponse,
  SkillPairsResponse,
  SkillsResponse,
  StartRunResponse,
  TrendsResponse,
} from './types';

export class ApiError extends Error {
  readonly status: number;
  readonly code: ErrorCode | 'network_error' | 'unknown';

  constructor(status: number, code: ApiError['code'], message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

const CODE_BY_STATUS: Record<number, ErrorCode> = {
  400: 'bad_request',
  401: 'unauthorized',
  403: 'forbidden',
  404: 'not_found',
  409: 'limit_reached',
  500: 'internal',
};

export type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

export interface ApiClientOptions {
  baseUrl: string;
  fetch?: FetchFn;
  /** Returns a fresh Cognito ID token, or null when signed out. */
  getIdToken: () => Promise<string | null>;
}

type Query = Record<string, string | number | undefined | null>;

interface RequestOptions {
  query?: Query;
  body?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/** Turns any non-2xx response into an ApiError, understanding both the app's error shape and
 * API Gateway's own `{"message": "Unauthorized"}` body. */
export async function toApiError(res: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  const fallbackCode = CODE_BY_STATUS[res.status] ?? (res.status >= 500 ? 'internal' : 'unknown');
  if (isRecord(body) && isRecord(body.error) && typeof body.error.code === 'string') {
    const message =
      typeof body.error.message === 'string' ? body.error.message : `Request failed (${res.status})`;
    return new ApiError(res.status, body.error.code as ErrorCode, message);
  }
  if (isRecord(body) && typeof body.message === 'string') {
    return new ApiError(res.status, fallbackCode, body.message);
  }
  return new ApiError(res.status, fallbackCode, `Request failed (${res.status})`);
}

function buildQuery(query: Query | undefined): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : '';
}

const enc = encodeURIComponent;

export function createApiClient(options: ApiClientOptions) {
  const baseUrl = options.baseUrl.replace(/\/+$/, '');
  const doFetch: FetchFn = options.fetch ?? ((input, init) => fetch(input, init));

  async function request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (path.startsWith('/me') || path.startsWith('/admin')) {
      const token = await options.getIdToken();
      if (!token) throw new ApiError(401, 'unauthorized', 'Please sign in to continue.');
      headers.Authorization = `Bearer ${token}`;
    }
    let body: string | undefined;
    if (opts.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(opts.body);
    }

    let res: Response;
    try {
      res = await doFetch(`${baseUrl}${path}${buildQuery(opts.query)}`, { method, headers, body });
    } catch {
      throw new ApiError(0, 'network_error', 'Could not reach the server. Check your connection.');
    }

    if (!res.ok) throw await toApiError(res);
    if (res.status === 204) return undefined as T;
    const text = await res.text();
    return (text ? JSON.parse(text) : undefined) as T;
  }

  return {
    getOverview: () => request<Overview>('GET', '/public/overview'),
    getSkills: () => request<SkillsResponse>('GET', '/public/skills'),
    getSkillList: () => request<SkillListResponse>('GET', '/public/skill-list'),
    getSalaries: (skill?: string) =>
      request<SalariesResponse>('GET', '/public/salaries', { query: { skill } }),
    getProvinces: () => request<ProvincesResponse>('GET', '/public/provinces'),
    getSkillPairs: () => request<SkillPairsResponse>('GET', '/public/skill-pairs'),
    getTrends: () => request<TrendsResponse>('GET', '/public/trends'),
    listJobs: (query: JobsQuery = {}) =>
      request<JobsPage>('GET', '/public/jobs', { query: { ...query } }),
    getJob: (jobId: string) => request<Job>('GET', `/public/jobs/${enc(jobId)}`),

    listSavedJobs: () => request<SavedJobsResponse>('GET', '/me/saved-jobs'),
    saveJob: (jobId: string) => request<SavedJob>('PUT', `/me/saved-jobs/${enc(jobId)}`),
    unsaveJob: (jobId: string) => request<void>('DELETE', `/me/saved-jobs/${enc(jobId)}`),
    listAlerts: () => request<AlertsResponse>('GET', '/me/alerts'),
    createAlert: (body: CreateAlertRequest) =>
      request<CreateAlertResponse>('POST', '/me/alerts', { body }),
    deleteAlert: (alertId: string) => request<void>('DELETE', `/me/alerts/${enc(alertId)}`),
    deleteMe: () => request<void>('DELETE', '/me'),

    startRun: () => request<StartRunResponse>('POST', '/admin/runs'),
    listRuns: () => request<RunsResponse>('GET', '/admin/runs'),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error && err.message) return err.message;
  return 'Something went wrong. Please try again.';
}
