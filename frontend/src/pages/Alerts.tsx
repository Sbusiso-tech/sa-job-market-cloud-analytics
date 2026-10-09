import { useCallback, useId, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, errorMessage } from '../api/client';
import {
  MAX_ALERT_SKILLS,
  MAX_ALERTS,
  PROVINCES,
  type AlertsResponse,
  type Province,
  type SubscriptionStatus,
} from '../api/types';
import { SkillPicker } from '../components/SkillPicker';
import { EmptyState, ErrorView, Loading, Notice } from '../components/StatusViews';
import { Card, PageHeader, SkillChip } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { formatDate } from '../lib/format';
import { useApi } from '../services';

function SubscriptionBanner({ status, email }: { status: SubscriptionStatus; email: string }) {
  if (status === 'pending_confirmation') {
    return (
      <Notice tone="warning" title="Confirm your email to start receiving alerts">
        AWS has sent a subscription confirmation email to <strong>{email || 'your inbox'}</strong> (subject “AWS
        Notification - Subscription Confirmation”). Please check your inbox, and your spam folder, and click the AWS
        confirmation link. Until then no alert emails can be delivered.
      </Notice>
    );
  }
  if (status === 'confirmed') {
    return (
      <Notice tone="success" title="Alerts are active">
        New matching jobs are emailed to <strong>{email}</strong> as one digest after each daily pipeline run.
      </Notice>
    );
  }
  return (
    <Notice tone="info" title="How alerts work">
      Pick up to {MAX_ALERT_SKILLS} skills and, if you like, a province. When you create your first alert, AWS emails
      you a confirmation link: click it once and you will get a digest of new matching jobs after each daily update.
    </Notice>
  );
}

export default function Alerts() {
  const api = useApi();
  const alerts = useAsync(useCallback(() => api.listAlerts(), [api]));
  const skillList = useAsync(useCallback(() => api.getSkillList(), [api]));
  const provinceId = useId();

  const [skills, setSkills] = useState<string[]>([]);
  const [province, setProvince] = useState<Province | ''>('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const data = alerts.data;
  const atLimit = (data?.alerts.length ?? 0) >= MAX_ALERTS;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (skills.length === 0) {
      setFormError('Choose at least one skill.');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    setSuccess(null);
    try {
      const res = await api.createAlert({ skills, ...(province ? { province } : {}) });
      alerts.setData((prev): AlertsResponse | undefined =>
        prev ? { ...prev, subscription_status: res.subscription_status, alerts: [...prev.alerts, res.alert] } : prev,
      );
      setSkills([]);
      setProvince('');
      setSuccess(`Alert created for ${res.alert.skills.join(', ')}${res.alert.province ? ` in ${res.alert.province}` : ''}.`);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'limit_reached') {
        setFormError(`You already have ${MAX_ALERTS} alerts, the maximum. Delete one to add another.`);
        alerts.reload();
      } else {
        setFormError(errorMessage(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(alertId: string) {
    setDeleting(alertId);
    setListError(null);
    setSuccess(null);
    try {
      await api.deleteAlert(alertId);
      alerts.setData((prev) => {
        if (!prev) return prev;
        const remaining = prev.alerts.filter((a) => a.alert_id !== alertId);
        return { ...prev, alerts: remaining, subscription_status: remaining.length === 0 ? 'none' : prev.subscription_status };
      });
    } catch (err) {
      setListError(errorMessage(err));
    } finally {
      setDeleting(null);
    }
  }

  if (!data) {
    return (
      <div>
        <PageHeader title="Job alerts" />
        {alerts.error ? <ErrorView error={alerts.error} onRetry={alerts.reload} /> : <Loading label="Loading your alerts…" />}
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Job alerts"
        subtitle="Get one email digest when new jobs match the skills (and province) you care about."
      />
      <div className="page-notice">
        <SubscriptionBanner status={data.subscription_status} email={data.email} />
      </div>

      <div className="grid grid--alerts">
        <Card title="New alert" subtitle={`You can have up to ${MAX_ALERTS} alerts.`}>
          {atLimit ? (
            <Notice tone="info" title="Alert limit reached">
              You have {MAX_ALERTS} alerts, the maximum. Delete one to add another.
            </Notice>
          ) : (
            <form className="form" onSubmit={handleSubmit} noValidate>
              {skillList.data ? (
                <SkillPicker
                  skills={skillList.data.skills}
                  selected={skills}
                  onChange={(next) => {
                    setSkills(next);
                    setFormError(null);
                  }}
                  max={MAX_ALERT_SKILLS}
                  disabled={submitting}
                />
              ) : skillList.error ? (
                <ErrorView error={skillList.error} onRetry={skillList.reload} title="Could not load skills" />
              ) : (
                <Loading label="Loading skills…" />
              )}
              <div className="field">
                <label htmlFor={provinceId}>
                  Province <span className="muted">(optional)</span>
                </label>
                <select
                  id={provinceId}
                  value={province}
                  onChange={(e) => setProvince(e.target.value as Province | '')}
                  disabled={submitting}
                >
                  <option value="">Any province</option>
                  {PROVINCES.filter((p) => p !== 'Unknown').map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>
              {formError && (
                <p className="form-error" role="alert">
                  {formError}
                </p>
              )}
              <button type="submit" className="btn btn--primary" disabled={submitting || skills.length === 0}>
                {submitting ? 'Creating…' : 'Create alert'}
              </button>
            </form>
          )}
          {success && (
            <p className="form-success" role="status">
              {success}
            </p>
          )}
        </Card>

        <Card title="Your alerts" subtitle={`${data.alerts.length} of ${MAX_ALERTS} used`}>
          {listError && (
            <p className="form-error" role="alert">
              {listError}
            </p>
          )}
          {data.alerts.length === 0 ? (
            <EmptyState title="No alerts yet">
              <p>
                Create one on this page, or look at the <Link to="/">dashboard</Link> to see which skills are in demand.
              </p>
            </EmptyState>
          ) : (
            <ul className="alert-list" aria-label="Your alerts">
              {data.alerts.map((a) => (
                <li key={a.alert_id} className="alert-item">
                  <div>
                    <div className="chip-row">
                      {a.skills.map((s) => (
                        <SkillChip key={s} tone="accent">
                          {s}
                        </SkillChip>
                      ))}
                    </div>
                    <p className="muted alert-item__meta">
                      {a.province ? a.province : 'Any province'} · created {formatDate(a.created_at)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn btn--ghost btn--sm btn--danger-text"
                    onClick={() => handleDelete(a.alert_id)}
                    disabled={deleting === a.alert_id}
                  >
                    {deleting === a.alert_id ? 'Deleting…' : 'Delete'}
                    <span className="visually-hidden"> alert for {a.skills.join(', ')}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
