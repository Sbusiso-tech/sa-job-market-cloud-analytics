import { useId, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Card, PageHeader } from '../components/ui';
import { useApi } from '../services';

const CONFIRM_WORD = 'DELETE';

export default function Account() {
  const { user, deleteUser } = useAuth();
  const api = useApi();
  const navigate = useNavigate();
  const confirmId = useId();
  const [open, setOpen] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete(event: FormEvent) {
    event.preventDefault();
    if (confirmText !== CONFIRM_WORD) return;
    setDeleting(true);
    setError(null);
    try {
      // Order matters: the API needs a valid token to delete the user's data first.
      await api.deleteMe();
      await deleteUser();
      navigate('/', { replace: true, state: { notice: 'Your account and all your data have been deleted.' } });
    } catch (err) {
      setError(errorMessage(err));
      setDeleting(false);
    }
  }

  if (!user) return null;

  return (
    <div className="narrow">
      <PageHeader title="Your account" />
      <Card title="Profile">
        <dl className="facts facts--single">
          <div>
            <dt>Email</dt>
            <dd>{user.email || '—'}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{user.isAdmin ? 'Administrator' : 'Member'}</dd>
          </div>
        </dl>
        <p className="hint">
          We only store your email address and a user id, plus the jobs you save and the alerts you create.
        </p>
      </Card>

      <Card title="Delete account" className="card--danger">
        <p>
          This permanently deletes your saved jobs, your alerts, your email subscription and your sign-in. It cannot be
          undone.
        </p>
        {!open ? (
          <button type="button" className="btn btn--danger" onClick={() => setOpen(true)}>
            Delete my account…
          </button>
        ) : (
          <form className="form" onSubmit={handleDelete}>
            <div className="field">
              <label htmlFor={confirmId}>
                Type <strong>{CONFIRM_WORD}</strong> to confirm
              </label>
              <input
                id={confirmId}
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                autoComplete="off"
                autoCapitalize="characters"
                disabled={deleting}
              />
            </div>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <div className="button-row">
              <button type="submit" className="btn btn--danger" disabled={deleting || confirmText !== CONFIRM_WORD}>
                {deleting ? 'Deleting…' : 'Permanently delete account'}
              </button>
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => {
                  setOpen(false);
                  setConfirmText('');
                  setError(null);
                }}
                disabled={deleting}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}
