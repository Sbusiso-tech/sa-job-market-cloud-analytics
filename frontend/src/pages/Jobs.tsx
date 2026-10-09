import { useCallback, useId, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { PROVINCES, type Job, type JobsPage, type Province } from '../api/types';
import { JobCard } from '../components/JobCard';
import { EmptyState, ErrorView, Loading } from '../components/StatusViews';
import { PageHeader } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { useApi } from '../services';

const PAGE_SIZE = 20;

function asProvince(value: string | null): Province | undefined {
  return value && (PROVINCES as readonly string[]).includes(value) ? (value as Province) : undefined;
}

interface MorePages {
  first: JobsPage | undefined;
  items: Job[];
  cursor: string | null;
}

export default function Jobs() {
  const api = useApi();
  const [params, setParams] = useSearchParams();
  const province = asProvince(params.get('province'));
  const skill = params.get('skill') ?? undefined;
  const provinceId = useId();
  const skillId = useId();

  const skillList = useAsync(useCallback(() => api.getSkillList(), [api]));
  const firstPage = useAsync(
    useCallback(() => api.listJobs({ province, skill, limit: PAGE_SIZE }), [api, province, skill]),
  );

  const [more, setMore] = useState<MorePages>({ first: undefined, items: [], cursor: null });
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState<string | null>(null);

  // Extra pages only count while they belong to the first page currently shown.
  const moreValid = more.first !== undefined && more.first === firstPage.data;
  const items = [...(firstPage.data?.items ?? []), ...(moreValid ? more.items : [])];
  const cursor = moreValid ? more.cursor : (firstPage.data?.next_cursor ?? null);

  function updateFilter(key: 'province' | 'skill', value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setMoreError(null);
    setParams(next, { replace: true });
  }

  async function loadMore() {
    if (!cursor || !firstPage.data) return;
    const first = firstPage.data;
    setLoadingMore(true);
    setMoreError(null);
    try {
      const page = await api.listJobs({ province, skill, limit: PAGE_SIZE, cursor });
      setMore((prev) => ({
        first,
        items: [...(prev.first === first ? prev.items : []), ...page.items],
        cursor: page.next_cursor,
      }));
    } catch (err) {
      setMoreError(errorMessage(err));
    } finally {
      setLoadingMore(false);
    }
  }

  const filtersActive = Boolean(province || skill);

  return (
    <div>
      <PageHeader title="Jobs" subtitle="The newest South African tech postings, collected daily." />

      <form className="filters card" role="search" aria-label="Filter jobs" onSubmit={(e) => e.preventDefault()}>
        <div className="field">
          <label htmlFor={provinceId}>Province</label>
          <select id={provinceId} value={province ?? ''} onChange={(e) => updateFilter('province', e.target.value)}>
            <option value="">All provinces</option>
            {PROVINCES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={skillId}>Skill</label>
          <select
            id={skillId}
            value={skill ?? ''}
            onChange={(e) => updateFilter('skill', e.target.value)}
            disabled={!skillList.data && !skill}
          >
            <option value="">{skillList.data || skill ? 'All skills' : 'Loading skills…'}</option>
            {skill && !skillList.data?.skills.some((s) => s.name === skill) && <option value={skill}>{skill}</option>}
            {skillList.data?.skills
              .slice()
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((s) => (
                <option key={s.name} value={s.name}>
                  {s.name}
                </option>
              ))}
          </select>
        </div>
        {filtersActive && (
          <button type="button" className="btn btn--ghost" onClick={() => setParams(new URLSearchParams(), { replace: true })}>
            Clear filters
          </button>
        )}
      </form>

      <div aria-live="polite" aria-busy={firstPage.loading}>
        {firstPage.loading && !firstPage.data ? (
          <Loading label="Loading jobs…" />
        ) : firstPage.error && !firstPage.loading ? (
          <ErrorView error={firstPage.error} onRetry={firstPage.reload} title="Could not load jobs" />
        ) : items.length === 0 && !cursor && !firstPage.loading ? (
          <EmptyState title="No jobs match these filters">
            {filtersActive ? <p>Try another province or skill.</p> : <p>Jobs appear after the first pipeline run.</p>}
          </EmptyState>
        ) : (
          <>
            {firstPage.loading && <Loading label="Updating…" />}
            <p className="result-count">
              {items.length === 0
                ? 'No matches among the newest postings yet. Load more to search older ones.'
                : `Showing ${items.length} job${items.length === 1 ? '' : 's'}${province ? ` in ${province}` : ''}${
                    skill ? ` asking for ${skill}` : ''
                  }`}
            </p>
            <ul className="job-list">
              {items.map((job) => (
                <li key={job.job_id}>
                  <JobCard job={job} highlightSkill={skill} />
                </li>
              ))}
            </ul>
            {moreError && (
              <p className="form-error" role="alert">
                {moreError}
              </p>
            )}
            {cursor && (
              <div className="load-more">
                <button type="button" className="btn btn--secondary" onClick={loadMore} disabled={loadingMore}>
                  {loadingMore ? 'Loading…' : 'Load more'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
