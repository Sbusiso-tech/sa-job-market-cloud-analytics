import { useId, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { AuthCard, PASSWORD_HINT } from '../components/AuthCard';
import { Notice } from '../components/StatusViews';

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : 'Something went wrong. Please try again.';
}

function ConfirmStep({ email, initialMessage }: { email: string; initialMessage?: string }) {
  const { service } = useAuth();
  const navigate = useNavigate();
  const codeId = useId();
  const emailId = useId();
  const [address, setAddress] = useState(email);
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(initialMessage ?? null);

  async function handleConfirm(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await service.confirmSignUp(address, code);
      navigate('/signin', { replace: true, state: { email: address, message: 'Email confirmed. You can sign in now.' } });
    } catch (err) {
      setError(messageOf(err));
      setBusy(false);
    }
  }

  async function handleResend() {
    setError(null);
    setInfo(null);
    try {
      await service.resendCode(address);
      setInfo(`A new code is on its way to ${address}.`);
    } catch (err) {
      setError(messageOf(err));
    }
  }

  return (
    <AuthCard
      title="Check your email"
      subtitle={
        <>
          We sent a 6-digit verification code to <strong>{address || 'your email'}</strong>.
        </>
      }
      footer={
        <p>
          Already confirmed? <Link to="/signin">Sign in</Link>
        </p>
      }
    >
      {info && (
        <div className="page-notice">
          <Notice tone="info">{info}</Notice>
        </div>
      )}
      <form className="form" onSubmit={handleConfirm}>
        {!email && (
          <div className="field">
            <label htmlFor={emailId}>Email</label>
            <input id={emailId} type="email" autoComplete="email" required value={address} onChange={(e) => setAddress(e.target.value)} />
          </div>
        )}
        <div className="field">
          <label htmlFor={codeId}>Verification code</label>
          <input
            id={codeId}
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]*"
            maxLength={6}
            required
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
          />
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn--primary btn--block" disabled={busy || code.length < 6}>
          {busy ? 'Confirming…' : 'Confirm email'}
        </button>
        <button type="button" className="btn btn--ghost btn--block" onClick={handleResend} disabled={!address}>
          Send a new code
        </button>
      </form>
    </AuthCard>
  );
}

export default function SignUp() {
  const { service } = useAuth();
  const [params, setParams] = useSearchParams();
  const location = useLocation();
  const emailId = useId();
  const passwordId = useId();
  const confirmId = useId();
  const hintId = useId();
  const [email, setEmail] = useState(params.get('email') ?? '');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (params.get('step') === 'confirm') {
    const message = (location.state as { message?: string } | null)?.message;
    return <ConfirmStep email={params.get('email') ?? ''} initialMessage={message} />;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError('The passwords do not match.');
      return;
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await service.signUp(email, password);
      setParams({ step: 'confirm', email: email.trim() });
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title="Create an account"
      subtitle="Free. We only store your email address."
      footer={
        <p>
          Already have an account? <Link to="/signin">Sign in</Link>
        </p>
      }
    >
      <form className="form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor={emailId}>Email</label>
          <input id={emailId} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor={passwordId}>Password</label>
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
        <div className="field">
          <label htmlFor={confirmId}>Confirm password</label>
          <input
            id={confirmId}
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
        <p className="field__hint">
          Already signed up but never confirmed?{' '}
          <Link to={`/signup?step=confirm${email ? `&email=${encodeURIComponent(email.trim())}` : ''}`}>Enter your code</Link>
        </p>
      </form>
    </AuthCard>
  );
}
