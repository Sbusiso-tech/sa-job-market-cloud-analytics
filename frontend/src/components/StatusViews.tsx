import type { ReactNode } from 'react';
import { errorMessage } from '../api/client';

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="status-view" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorView({ error, onRetry, title = 'Could not load this' }: { error: unknown; onRetry?: () => void; title?: string }) {
  return (
    <div className="notice notice--error" role="alert">
      <div>
        <strong>{title}</strong>
        <p>{errorMessage(error)}</p>
      </div>
      {onRetry && (
        <button type="button" className="btn btn--secondary btn--sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty-state">
      <svg className="empty-state__icon" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
        <rect x="6" y="26" width="8" height="14" rx="2" fill="#FFB612" />
        <rect x="20" y="16" width="8" height="24" rx="2" fill="#002395" opacity="0.85" />
        <rect x="34" y="8" width="8" height="32" rx="2" fill="#007A4D" />
      </svg>
      <h3>{title}</h3>
      {children && <div className="empty-state__body">{children}</div>}
    </div>
  );
}

export function Notice({ tone = 'info', children, title }: { tone?: 'info' | 'success' | 'warning' | 'error'; title?: string; children: ReactNode }) {
  return (
    <div className={`notice notice--${tone}`} role={tone === 'error' || tone === 'warning' ? 'alert' : 'status'}>
      <div>
        {title && <strong>{title}</strong>}
        <div>{children}</div>
      </div>
    </div>
  );
}
