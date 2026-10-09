import { useId, type ReactNode } from 'react';
import type { AsyncState } from '../hooks/useAsync';
import { EmptyState, ErrorView, Loading } from './StatusViews';

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="page-header__subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </div>
  );
}

export function Card({ title, subtitle, children, className, actions }: { title: string; subtitle?: ReactNode; children: ReactNode; className?: string; actions?: ReactNode }) {
  const id = useId();
  return (
    <section className={className ? `card ${className}` : 'card'} aria-labelledby={id}>
      <header className="card__header">
        <div>
          <h2 id={id}>{title}</h2>
          {subtitle && <p className="card__subtitle">{subtitle}</p>}
        </div>
        {actions}
      </header>
      {children}
    </section>
  );
}

export function StatCard({ label, value, hint, accent = 'green' }: { label: string; value: ReactNode; hint?: ReactNode; accent?: 'green' | 'gold' | 'blue' | 'red' }) {
  return (
    <div className={`stat-card stat-card--${accent}`}>
      <span className="stat-card__label">{label}</span>
      <span className="stat-card__value">{value}</span>
      {hint && <span className="stat-card__hint">{hint}</span>}
    </div>
  );
}

/** Renders loading, error and empty states for one async block, then `children(data)`. */
export function AsyncBlock<T>({
  state,
  isEmpty,
  emptyTitle = 'Nothing to show yet',
  emptyText,
  children,
}: {
  state: AsyncState<T>;
  isEmpty?: (data: T) => boolean;
  emptyTitle?: string;
  emptyText?: ReactNode;
  children: (data: T) => ReactNode;
}) {
  if (state.data === undefined) {
    if (state.error) return <ErrorView error={state.error} onRetry={state.reload} />;
    return <Loading />;
  }
  if (isEmpty?.(state.data)) return <EmptyState title={emptyTitle}>{emptyText}</EmptyState>;
  return (
    <>
      {state.error !== undefined && <ErrorView error={state.error} onRetry={state.reload} title="Could not refresh" />}
      {children(state.data)}
    </>
  );
}

export function SkillChip({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'accent' }) {
  return <span className={tone === 'accent' ? 'chip chip--accent' : 'chip'}>{children}</span>;
}
