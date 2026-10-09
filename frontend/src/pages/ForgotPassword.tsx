import { useId, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { AuthCard, PASSWORD_HINT } from '../components/AuthCard';
import { Notice } from '../components/StatusViews';

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : 'Something went wrong. Please try again.';
}

export default function ForgotPassword() {
  const { service } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const emailId = useId();
  const codeId = useId();
  const passwordId = useId();
  const hintId = useId();
  const [step, setStep] = useState<'request' | 'reset'>('request');
  const [email, setEmail] = useState((location.state as { email?: string } | null)?.email ?? '');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function requestCode(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await service.forgotPassword(email);
      setStep('reset');
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  async function resetPassword(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await service.confirmForgotPassword(email, code, password);
      navigate('/signin', { replace: true, state: { email, message: 'Password changed. Sign in with your new password.' } });
    } catch (err) {
      setError(messageOf(err));
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Reset your password"
      subtitle={step === 'request' ? 'We will email you a code to set a new password.' : undefined}
      footer={
        <p>
          Remembered it? <Link to="/signin">Back to sign in</Link>
        </p>
      }
    >
      {step === 'request' ? (
        <form className="form" onSubmit={requestCode}>
          <div className="field">
            <label htmlFor={emailId}>Email</label>
            <input id={emailId} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn btn--primary btn--block" disabled={busy || !email}>
            {busy ? 'Sending…' : 'Send reset code'}
          </button>
        </form>
      ) : (
        <form className="form" onSubmit={resetPassword}>
          <div className="page-notice">
            <Notice tone="info">
              If an account exists for <strong>{email}</strong>, a 6-digit code is on its way.
            </Notice>
          </div>
          <div className="field">
            <label htmlFor={codeId}>Code</label>
            <input
              id={codeId}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            />
          </div>
          <div className="field">
            <label htmlFor={passwordId}>New password</label>
            <input
              id={passwordId}
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              aria-describedby={hintId}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <p id={hintId} className="field__hint">
              {PASSWORD_HINT}
            </p>
          </div>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn btn--primary btn--block" disabled={busy || code.length < 6 || password.length < 8}>
            {busy ? 'Saving…' : 'Set new password'}
          </button>
          <button type="button" className="btn btn--ghost btn--block" onClick={() => setStep('request')} disabled={busy}>
            Use a different email
          </button>
        </form>
      )}
    </AuthCard>
  );
}
