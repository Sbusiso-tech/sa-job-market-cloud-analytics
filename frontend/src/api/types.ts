// Request and response shapes mirror docs/api-contract.md exactly (snake_case field names).
// Change that document first, then this file, so the backend and web app stay in step.

export const PROVINCES = [
  'Gauteng',
  'Western Cape',
  'KwaZulu-Natal',
  'Eastern Cape',
  'Free State',
  'Limpopo',
  'Mpumalanga',
  'North West',
  'Northern Cape',
  'Remote',
  'Unknown',
] as const;
export type Province = (typeof PROVINCES)[number];

export type Seniority = 'intern' | 'junior' | 'mid' | 'senior' | 'lead' | 'unspecified';
export type EmploymentType =
  | 'full_time'
  | 'part_time'
  | 'contract'
  | 'internship'
  | 'temporary'
  | 'unspecified';

export type ErrorCode =
  | 'bad_request'
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'limit_reached'
  | 'internal';

export interface ErrorBody {
  error: { code: ErrorCode; message: string };
}

export interface NameCount<N extends string = string> {
  name: N;
  count: number;
}

// Public routes. Before the first pipeline run every route returns the same shape with
// zeros, nulls and empty lists.

export interface Overview {
  last_updated: string | null;
  window_days: number;
  total_jobs: number;
  new_this_week: number;
  median_salary_zar: number | null;
  top_skill: string | null;
  top_province: Province | null;
  seniority: NameCount<Seniority>[];
  employment_type: NameCount<EmploymentType>[];
}

export interface SkillStat {
  skill: string;
  category: string;
  count: number;
  share: number;
  change_vs_prev_week: number;
}

export interface SkillsResponse {
  last_updated: string | null;
  skills: SkillStat[];
}

export interface SkillListItem {
  name: string;
  category: string;
}

export interface SkillListResponse {
  skills: SkillListItem[];
}

export interface SalaryStat {
  skill: string;
  sample_size: number;
  p25: number;
  median: number;
  p75: number;
}

export interface SalariesResponse {
  last_updated: string | null;
  salaries: SalaryStat[];
}

export interface SkillCount {
  skill: string;
  count: number;
}

export interface ProvinceStat {
  province: Province;
  count: number;
  median_salary_zar: number | null;
  top_skills: SkillCount[];
}

export interface ProvincesResponse {
  last_updated: string | null;
  provinces: ProvinceStat[];
}

export interface SkillPair {
  skills: [string, string];
  count: number;
}

export interface SkillPairsResponse {
  last_updated: string | null;
  pairs: SkillPair[];
}

export interface TrendWeek {
  week: string;
  total_jobs: number;
  top_skills: SkillCount[];
}

export interface TrendsResponse {
  last_updated: string | null;
  weeks: TrendWeek[];
}

// company and description_snippet are '' when unknown; the nullable fields are null when unknown.
export interface Job {
  job_id: string;
  title: string;
  company: string;
  location: string | null;
  city: string | null;
  province: Province;
  is_remote: boolean;
  salary_min_zar: number | null;
  salary_max_zar: number | null;
  salary_is_predicted: boolean;
  seniority: Seniority;
  employment_type: EmploymentType;
  experience_years_min: number | null;
  experience_years_max: number | null;
  skills: string[];
  date_posted: string | null;
  url: string | null;
  source: string;
  description_snippet: string;
}

export interface JobsQuery {
  province?: Province;
  skill?: string;
  limit?: number;
  cursor?: string;
}

export interface JobsPage {
  items: Job[];
  next_cursor: string | null;
}

// Signed-in user routes.

export interface SavedJob {
  job_id: string;
  title: string;
  company: string;
  province: Province;
  saved_at: string;
}

export interface SavedJobsResponse {
  items: SavedJob[];
}

export type SubscriptionStatus = 'none' | 'pending_confirmation' | 'confirmed';

export interface Alert {
  alert_id: string;
  skills: string[];
  province: Province | null;
  created_at: string;
}

export interface AlertsResponse {
  email: string;
  subscription_status: SubscriptionStatus;
  alerts: Alert[];
}

export interface CreateAlertRequest {
  skills: string[];
  province?: Province;
}

export interface CreateAlertResponse {
  alert: Alert;
  subscription_status: SubscriptionStatus;
}

// Admin routes.

export interface StartRunResponse {
  execution_id: string;
  started_at: string;
}

export type RunStatus = 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'TIMED_OUT' | 'ABORTED';

export interface PipelineRun {
  execution_id: string;
  status: RunStatus;
  started_at: string;
  stopped_at: string | null;
  fetched: number | null;
  new_jobs: number | null;
  failed: number | null;
}

export interface RunsResponse {
  dlq_depth: number;
  runs: PipelineRun[];
}

export const MAX_ALERTS = 5;
export const MAX_ALERT_SKILLS = 5;
