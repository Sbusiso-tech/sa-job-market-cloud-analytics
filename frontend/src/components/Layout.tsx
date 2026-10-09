import { Suspense, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useServices } from '../services';
import { GITHUB_URL } from '../lib/constants';
import { Loading, Notice } from './StatusViews';

function Brand() {
  return (
    <Link to="/" className="brand" aria-label="SA Job Market home">
      <svg viewBox="0 0 32 32" className="brand__logo" aria-hidden="true" focusable="false">
        <rect width="32" height="32" rx="8" fill="#002395" />
        <rect x="6" y="17" width="5" height="9" rx="1.5" fill="#FFB612" />
        <rect x="13.5" y="11" width="5" height="15" rx="1.5" fill="#FFFFFF" />
        <rect x="21" y="6" width="5" height="20" rx="1.5" fill="#007A4D" />
      </svg>
      <span className="brand__text">
        SA Job Market <span className="brand__sub">Analytics</span>
      </span>
    </Link>
  );
}

export function Layout() {
  const { status, user, signOut } = useAuth();
  const { config } = useServices();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const notice = (location.state as { notice?: string } | null)?.notice;

  const close = () => setMenuOpen(false);
  const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? 'nav-link nav-link--active' : 'nav-link');

  async function handleSignOut() {
    close();
    await signOut();
    navigate('/', { replace: true });
  }

  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="site-header">
        <div className="flag-stripe" aria-hidden="true" />
        <div className="container site-header__inner">
          <Brand />
          <button
            type="button"
            className="nav-toggle"
            aria-expanded={menuOpen}
            aria-controls="site-nav"
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span className="nav-toggle__bars" aria-hidden="true" />
            <span className="visually-hidden">{menuOpen ? 'Close menu' : 'Open menu'}</span>
          </button>
          <nav id="site-nav" className={menuOpen ? 'site-nav site-nav--open' : 'site-nav'} aria-label="Main">
            <ul className="site-nav__links">
              <li>
                <NavLink to="/" end className={linkClass} onClick={close}>
                  Dashboard
                </NavLink>
              </li>
              <li>
                <NavLink to="/jobs" className={linkClass} onClick={close}>
                  Jobs
                </NavLink>
              </li>
              {status === 'signedIn' && (
                <>
                  <li>
                    <NavLink to="/saved" className={linkClass} onClick={close}>
                      Saved
                    </NavLink>
                  </li>
                  <li>
                    <NavLink to="/alerts" className={linkClass} onClick={close}>
                      Alerts
                    </NavLink>
                  </li>
                </>
              )}
              {user?.isAdmin && (
                <li>
                  <NavLink to="/admin" className={linkClass} onClick={close}>
                    Admin
                  </NavLink>
                </li>
              )}
              <li>
                <NavLink to="/about" className={linkClass} onClick={close}>
                  About
                </NavLink>
              </li>
            </ul>
            <div className="site-nav__account">
              {status === 'signedIn' && user ? (
                <>
                  <NavLink to="/account" className={linkClass} onClick={close} title={user.email}>
                    Account
                  </NavLink>
                  <button type="button" className="btn btn--ghost btn--sm" onClick={handleSignOut}>
                    Sign out
                  </button>
                </>
              ) : status === 'signedOut' ? (
                <>
                  <NavLink to="/signin" className={linkClass} onClick={close}>
                    Sign in
                  </NavLink>
                  <Link to="/signup" className="btn btn--primary btn--sm" onClick={close}>
                    Sign up
                  </Link>
                </>
              ) : null}
            </div>
          </nav>
        </div>
      </header>

      {config.useMocks && (
        <div className="demo-banner" role="note">
          <div className="container">
            <strong>Demo mode:</strong> the data is fake and nothing leaves your browser. Sign in with any email and
            password; use an email containing “admin” to see the admin area.
          </div>
        </div>
      )}

      <main id="main" className="container site-main" tabIndex={-1}>
        {notice && (
          <div className="page-notice">
            <Notice tone="warning">{notice}</Notice>
          </div>
        )}
        <Suspense fallback={<Loading />}>
          <Outlet />
        </Suspense>
      </main>

      <footer className="site-footer">
        <div className="container site-footer__inner">
          <p>
            Built on AWS serverless: CloudFront, API Gateway, Lambda, DynamoDB, Step Functions, SQS, SNS and Cognito.
          </p>
          <p>
            <Link to="/about">About this project</Link>
            <span aria-hidden="true"> · </span>
            <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
              Source on GitHub
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}
