import { useCallback, useEffect, useState } from 'react';
import { errorMessage } from '../api/client';
import type { RunStatus } from '../api/types';
import { EmptyState, ErrorView, Loading, Notice } from '../components/StatusViews';
import { Card, PageHeader } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { formatDateTime, formatDuration, formatNumber } from '../lib/format';
import { useApi } from '../services';

const POLL_MS = 10_000;

const STATUS_CLASS: Record<RunStatus, string> = {
  RUNNING: 'badge--blue',
  SUCCEEDED: 'badge--green',
  FAILED: 'badge--red',
  TIMED_OUT: 'badge--red',
  ABORTED: 'badge--gold',
};

function StatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`badge ${STATUS_CLASS[status] ?? ''}`}>
      {status === 'RUNNING' && <span className="pulse" aria-hidden="true" />}
      {status.replace('_', ' ').toLowerCase()}
    </span>
  );
}

export default function Admin() {
  const api = useApi();
  const runs = useAsync(useCallback(() => api.listRuns(), [api]));
  const [starting, setStarting] = useState(false);
  const [message, setMessage] = useState<{ tone: 'success' | 'error'; text: string } | null>(null);

  const anyRunning = runs.data?.runs.some((r) => r.status === 'RUNNING') ?? false;
  const { reload } = runs;

  useEffect(() => {
    if (!anyRunning) return;
    const timer = setInterval(reload, POLL_MS);
    return () => clearInterval(timer);
  }, [anyRunning, reload]);

  async function startRun() {
    setStarting(true);
    setMessage(null);
    try {
      const res = await api.startRun();
      setMessage({ tone: 'success', text: `Pipeline started (${res.execution_id}). This page refreshes while it runs.` });
      reload();
    } catch (err) {
      setMessage({ tone: 'error', text: errorMessage(err) });
    } finally {
      setStarting(false);
    }
  }

  const data = runs.data;

  return (
    <div>
      <PageHeader
        title="Admin"
        subtitle="Start the data pipeline and check recent runs. It also runs every day at 05:00 SAST."
        actions={
          <button type="button" className="btn btn--primary" onClick={startRun} disabled={starting || anyRunning}>
            {starting ? 'Starting…' : anyRunning ? 'Run in progress…' : 'Run pipeline now'}
          </button>
        }
      />

      {message && (
        <div className="page-notice">
          <Notice tone={message.tone}>{message.text}</Notice>
        </div>
      )}

      {!data ? (
        runs.error ? (
          <ErrorView error={runs.error} onRetry={reload} />
        ) : (
          <Loading label="Loading pipeline runs…" />
        )
      ) : (
        <>
          <div className="page-notice">
            {data.dlq_depth > 0 ? (
              <Notice tone="warning" title="Dead-letter queue has messages">
                {formatNumber(data.dlq_depth)} job message{data.dlq_depth === 1 ? '' : 's'} failed processing and{' '}
                {data.dlq_depth === 1 ? 'is' : 'are'} waiting in the dead-letter queue. Check the Process Lambda logs in
                CloudWatch, then redrive or purge the queue.
              </Notice>
            ) : (
              <Notice tone="success">Dead-letter queue is empty: every job message was processed.</Notice>
            )}
          </div>

          <Card
            title="Recent runs"
            subtitle="Last 20 executions, newest first"
            actions={
              <button type="button" className="btn btn--ghost btn--sm" onClick={reload} disabled={runs.loading}>
                {runs.loading ? 'Refreshing…' : 'Refresh'}
              </button>
            }
          >
            {runs.error !== undefined && <ErrorView error={runs.error} onRetry={reload} title="Could not refresh" />}
            {data.runs.length === 0 ? (
              <EmptyState title="No runs yet">
                <p>Start the first run with the button above.</p>
              </EmptyState>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Execution</th>
                      <th scope="col">Status</th>
                      <th scope="col">Started</th>
                      <th scope="col">Duration</th>
                      <th scope="col" className="num">Fetched</th>
                      <th scope="col" className="num">New jobs</th>
                      <th scope="col" className="num">Failed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.runs.map((r) => (
                      <tr key={r.execution_id}>
                        <th scope="row" className="mono">
                          {r.execution_id}
                        </th>
                        <td>
                          <StatusBadge status={r.status} />
                        </td>
                        <td>{formatDateTime(r.started_at)}</td>
                        <td>{r.status === 'RUNNING' ? '…' : formatDuration(r.started_at, r.stopped_at)}</td>
                        <td className="num">{formatNumber(r.fetched)}</td>
                        <td className="num">{formatNumber(r.new_jobs)}</td>
                        <td className={r.failed ? 'num text-danger' : 'num'}>{formatNumber(r.failed)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
