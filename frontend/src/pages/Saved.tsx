import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { EmptyState, ErrorView, Loading } from '../components/StatusViews';
import { PageHeader } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { formatRelative } from '../lib/format';
import { useApi } from '../services';

export default function Saved() {
  const api = useApi();
  const saved = useAsync(useCallback(() => api.listSavedJobs(), [api]));
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function remove(jobId: string) {
    setRemoving(jobId);
    setError(null);
    try {
      await api.unsaveJob(jobId);
      saved.setData((prev) => (prev ? { items: prev.items.filter((i) => i.job_id !== jobId) } : prev));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRemoving(null);
    }
  }

  return (
    <div>
      <PageHeader title="Saved jobs" subtitle="Jobs you have bookmarked. Postings expire after about 60 days." />
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!saved.data ? (
        saved.error ? (
          <ErrorView error={saved.error} onRetry={saved.reload} />
        ) : (
          <Loading label="Loading saved jobs…" />
        )
      ) : saved.data.items.length === 0 ? (
        <EmptyState title="No saved jobs yet">
          <p>Open any job and press “Save job” to keep it here.</p>
          <p>
            <Link to="/jobs" className="btn btn--primary">
              Browse jobs
            </Link>
          </p>
        </EmptyState>
      ) : (
        <ul className="saved-list">
          {saved.data.items.map((item) => (
            <li key={item.job_id} className="saved-item card">
              <div>
                <h2 className="saved-item__title">
                  <Link to={`/jobs/${encodeURIComponent(item.job_id)}`}>{item.title}</Link>
                </h2>
                <p className="muted">
                  {[item.company, item.province, `saved ${formatRelative(item.saved_at)}`].filter(Boolean).join(' · ')}
                </p>
              </div>
              <button
                type="button"
                className="btn btn--ghost btn--sm"
                onClick={() => remove(item.job_id)}
                disabled={removing === item.job_id}
              >
                {removing === item.job_id ? 'Removing…' : 'Remove'}
                <span className="visually-hidden"> {item.title}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
