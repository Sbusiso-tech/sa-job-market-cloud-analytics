import type { ReactNode } from 'react';

export function AuthCard({ title, subtitle, children, footer }: { title: string; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="auth-page">
      <div className="auth-card card">
        <div className="flag-stripe flag-stripe--card" aria-hidden="true" />
        <h1>{title}</h1>
        {subtitle && <p className="auth-card__subtitle">{subtitle}</p>}
        {children}
        {footer && <div className="auth-card__footer">{footer}</div>}
      </div>
    </div>
  );
}

export const PASSWORD_HINT = 'At least 8 characters with upper and lower case letters, a number and a symbol.';
