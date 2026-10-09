import { useCallback, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { ApiError, errorMessage } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { EmptyState, ErrorView, Loading } from '../components/StatusViews';
import { SkillChip } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import {
  employmentLabel,
  experienceLabel,
  formatDate,
  formatRelative,
  formatSalaryRange,
  seniorityLabel,
} from '../lib/format';
import { safeExternalUrl } from '../lib/url';
import { useApi } from '../services';

export default function JobDetail() {
  const { jobId = '' } = useParams();
  const api = useApi();
  const { status } = useAuth();
  const location = useLocation();
  const signedIn = status === 'signedIn';

  const job = useAsync(useCallback(() => api.getJob(jobId), [api, jobId]));
  const saved = useAsync(
    useCallback(() => (signedIn ? api.listSavedJobs() : Promise.resolve(null)), [api, signedIn]),
  );
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const isSaved = Boolean(saved.data?.items.some((i) => i.job_id === jobId));

  async function toggleSave() {
    setSaving(true);
    setSaveError(null);
    try {
      if (isSaved) {
        await api.unsaveJob(jobId);
        saved.setData((prev) => (prev ? { items: prev.items.filter((i) => i.job_id !== jobId) } : prev));
      } else {
        const item = await api.saveJob(jobId);
        saved.setData((prev) => ({ items: [item, ...(prev?.items ?? []).filter((i) => i.job_id !== jobId)] }));
      }
    } catch (err) {
      setSaveError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (!job.data) {
    if (job.error instanceof ApiError && job.error.code === 'not_found') {
      return (
        <EmptyState title="Job not found">
          <p>This posting may have expired or been removed.</p>
          <p>
            <Link to="/jobs" className="btn btn--secondary">
              Back to jobs
            </Link>
          </p>
        </EmptyState>
      );
    }
    if (job.error) return <ErrorView error={job.error} onRetry={job.reload} title="Could not load this job" />;
    return <Loading label="Loading job…" />;
  }

  const j = job.data;
  const salary = formatSalaryRange(j.salary_min_zar, j.salary_max_zar);
  const experience = experienceLabel(j.experience_years_min, j.experience_years_max);
  const externalUrl = safeExternalUrl(j.url);

  return (
    <article className="job-detail">
      <p className="breadcrumb">
        <Link to="/jobs">← All jobs</Link>
      </p>
      <header className="job-detail__header card">
        <div>
          <h1>{j.title}</h1>
          <p className="job-detail__company">{[j.company, j.location].filter(Boolean).join(' · ')}</p>
          <p className="muted">
            {j.date_posted && (
              <>
                Posted{' '}
                <time dateTime={j.date_posted} title={formatDate(j.date_posted)}>
                  {formatRelative(j.date_posted)}
                </time>{' '}
              </>
            )}
            {j.date_posted ? 'via' : 'Via'} {j.source === 'adzuna' ? 'Adzuna' : j.source}
          </p>
        </div>
        <div className="job-detail__actions">
          {externalUrl && (
            <a className="btn btn--primary" href={externalUrl} target="_blank" rel="noopener noreferrer">
              View and apply <span className="visually-hidden">(opens in a new tab)</span>
              <span aria-hidden="true"> ↗</span>
            </a>
          )}
          {signedIn ? (
            <button
              type="button"
              className={isSaved ? 'btn btn--secondary btn--saved' : 'btn btn--secondary'}
              onClick={toggleSave}
              disabled={saving || saved.data === undefined}
              aria-pressed={isSaved}
            >
              {saving ? 'Saving…' : isSaved ? '★ Saved' : '☆ Save job'}
            </button>
          ) : status === 'signedOut' ? (
            <Link className="btn btn--ghost" to="/signin" state={{ from: location.pathname }}>
              Sign in to save
            </Link>
          ) : null}
        </div>
        {saveError && (
          <p className="form-error" role="alert">
            {saveError}
          </p>
        )}
      </header>

      <div className="grid grid--detail">
        <section className="card" aria-labelledby="job-facts">
          <h2 id="job-facts">At a glance</h2>
          <dl className="facts">
            <div>
              <dt>Salary (per year)</dt>
              <dd>
                {salary ?? 'Not given'}
                {salary && j.salary_is_predicted && (
                  <span className="badge badge--gold" title="Adzuna's estimate; the advert did not state a salary">
                    estimate
                  </span>
                )}
              </dd>
            </div>
            <div>
              <dt>Province</dt>
              <dd>{j.province}</dd>
            </div>
            <div>
              <dt>Seniority</dt>
              <dd>{seniorityLabel(j.seniority)}</dd>
            </div>
            <div>
              <dt>Employment type</dt>
              <dd>{employmentLabel(j.employment_type)}</dd>
            </div>
            <div>
              <dt>Experience</dt>
              <dd>{experience ?? 'Not stated'}</dd>
            </div>
            <div>
              <dt>Remote</dt>
              <dd>{j.is_remote ? 'Yes' : 'No'}</dd>
            </div>
          </dl>
        </section>
        <section className="card" aria-labelledby="job-about">
          <h2 id="job-about">About the role</h2>
          <p className="job-detail__snippet">{j.description_snippet || 'No description available.'}</p>
          <h3>Skills mentioned</h3>
          {j.skills.length > 0 ? (
            <div className="chip-row">
              {j.skills.map((s) => (
                <Link key={s} to={`/jobs?skill=${encodeURIComponent(s)}`} className="chip chip--link">
                  {s}
                </Link>
              ))}
            </div>
          ) : (
            <p className="muted">No known skills were detected.</p>
          )}
          {signedIn && j.skills.length > 0 && (
            <p className="hint">
              Want to hear about jobs like this? <Link to="/alerts">Create an alert</Link> for these skills.
            </p>
          )}
          {!signedIn && j.skills.length > 0 && (
            <p className="hint">
              <SkillChip tone="accent">Tip</SkillChip> Sign in to get email alerts for new jobs with these skills.
            </p>
          )}
        </section>
      </div>
    </article>
  );
}
