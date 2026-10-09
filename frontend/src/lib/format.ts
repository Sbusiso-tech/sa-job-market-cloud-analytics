import type { EmploymentType, Seniority } from '../api/types';

const zar = new Intl.NumberFormat('en-ZA', { style: 'currency', currency: 'ZAR', maximumFractionDigits: 0 });
const zarCompact = new Intl.NumberFormat('en-ZA', {
  style: 'currency',
  currency: 'ZAR',
  notation: 'compact',
  maximumFractionDigits: 1,
});
const integer = new Intl.NumberFormat('en-ZA', { maximumFractionDigits: 0 });
const percent = new Intl.NumberFormat('en-ZA', { style: 'percent', maximumFractionDigits: 1 });
const dateFmt = new Intl.DateTimeFormat('en-ZA', { day: 'numeric', month: 'short', year: 'numeric' });
const dateTimeFmt = new Intl.DateTimeFormat('en-ZA', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

export function formatZar(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : zar.format(value);
}

export function formatZarCompact(value: number): string {
  return zarCompact.format(value);
}

export function formatSalaryRange(min: number | null, max: number | null): string | null {
  if (min === null && max === null) return null;
  if (min !== null && max !== null && min !== max) return `${zar.format(min)} – ${zar.format(max)}`;
  return zar.format((min ?? max) as number);
}

export function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : integer.format(value);
}

export function formatPercent(share: number): string {
  return percent.format(share);
}

export function formatSignedChange(change: number): string {
  if (change > 0) return `+${integer.format(change)}`;
  if (change < 0) return `−${integer.format(Math.abs(change))}`;
  return '0';
}

function parseDate(iso: string): Date | null {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(iso: string | null | undefined): string {
  const d = iso ? parseDate(iso) : null;
  return d ? dateFmt.format(d) : '—';
}

export function formatDateTime(iso: string | null | undefined): string {
  const d = iso ? parseDate(iso) : null;
  return d ? dateTimeFmt.format(d) : '—';
}

export function formatRelative(iso: string | null | undefined, now: number = Date.now()): string {
  const d = iso ? parseDate(iso) : null;
  if (!d) return '—';
  const diffMs = now - d.getTime();
  const minutes = Math.round(diffMs / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return 'yesterday';
  if (days < 30) return `${days} days ago`;
  return formatDate(iso);
}

export function formatDuration(startIso: string, endIso: string | null): string {
  const start = parseDate(startIso);
  const end = endIso ? parseDate(endIso) : null;
  if (!start || !end) return '—';
  const seconds = Math.max(0, Math.round((end.getTime() - start.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

const SENIORITY_LABELS: Record<Seniority, string> = {
  intern: 'Intern',
  junior: 'Junior',
  mid: 'Mid-level',
  senior: 'Senior',
  lead: 'Lead',
  unspecified: 'Not specified',
};

const EMPLOYMENT_LABELS: Record<EmploymentType, string> = {
  full_time: 'Full-time',
  part_time: 'Part-time',
  contract: 'Contract',
  internship: 'Internship',
  temporary: 'Temporary',
  unspecified: 'Not specified',
};

export function seniorityLabel(value: Seniority): string {
  return SENIORITY_LABELS[value] ?? value;
}

export function employmentLabel(value: EmploymentType): string {
  return EMPLOYMENT_LABELS[value] ?? value;
}

export function experienceLabel(min: number | null, max: number | null): string | null {
  if (min === null && max === null) return null;
  if (min !== null && max !== null) return min === max ? `${min} years` : `${min}–${max} years`;
  if (min !== null) return `${min}+ years`;
  return `Up to ${max} years`;
}
