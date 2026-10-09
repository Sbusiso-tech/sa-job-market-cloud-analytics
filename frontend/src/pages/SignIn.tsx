import { useId, useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { AuthError } from '../auth/service';
import { AuthCard } from '../components/AuthCard';
import { Notice } from '../components/StatusViews';
import { useServices } from '../services';

interface LocationState {
  from?: string;
  email?: string;
  message?: string;
}

export default function SignIn() {
  const { signIn, status } = useAuth();
  const { config } = useServices();
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as LocationState | null) ?? {};
  const from = state.from && state.from.startsWith('/') && !state.from.startsWith('//') ? state.from : '/';

  const emailId = useId();
  const passwordId = useId();
  const [email, setEmail] = useState(state.email ?? '');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === 'signedIn' && !busy) return <Navigate to={from} replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setBusy(false);
      if (err instanceof AuthError && err.code === 'not_confirmed') {
        navigate(`/signup?step=confirm&email=${encodeURIComponent(email.trim())}`, {
          state: { message: 'Please confirm your email first. Enter the code we sent you.' },
        });
        return;
      }
      setError(err instanceof Error ? err.message : 'Sign-in failed.');
    }
  }

  return (
    <AuthCard
      title="Sign in"
      subtitle="Save jobs and get email alerts for the skills you care about."
      footer={
        <p>
          New here? <Link to="/signup">Create an account</Link>
        </p>
      }
    >
      {state.message && (
        <div className="page-notice">
          <Notice tone="success">{state.message}</Notice>
        </div>
      )}
      {config.useMocks && (
        <p className="hint">Demo mode: any email and password work. Include “admin” in the email to be an admin.</p>
      )}
      <form className="form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor={emailId}>Email</label>
          <input
            id={emailId}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <div className="field__label-row">
            <label htmlFor={passwordId}>Password</label>
            <Link to="/forgot-password" state={{ email }} className="small-link">
              Forgot password?
            </Link>
          </div>
          <input
            id={passwordId}
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn--primary btn--block" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthCard>
  );
}
