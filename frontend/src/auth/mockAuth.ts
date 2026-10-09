import { AuthError, type AuthService, type Session } from './service';
import { ADMIN_GROUP, isExpired, makeUnsignedToken, parseJwtClaims, userFromIdToken } from './tokens';

export const MOCK_SESSION_KEY = 'sajm.mock-session';
const TOKEN_TTL_SECONDS = 60 * 60;

/** Stable fake `sub` per email (FNV-1a), formatted like a UUID. */
function sub(email: string): string {
  let hex = '';
  for (let round = 0; round < 4; round++) {
    let h = 0x811c9dc5 ^ round;
    for (const ch of email) {
      h ^= ch.charCodeAt(0);
      h = Math.imul(h, 0x01000193);
    }
    hex += (h >>> 0).toString(16).padStart(8, '0');
  }
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`;
}

/**
 * Offline stand-in for Cognito: any email and password sign in, and an email containing
 * "admin" is placed in the admins group. Tokens are unsigned and only accepted by the mock API.
 */
export function createMockAuth(storage: Storage = window.sessionStorage): AuthService {
  function wait() {
    return new Promise((resolve) => setTimeout(resolve, 250));
  }

  function issue(email: string): Session {
    const normalised = email.trim().toLowerCase();
    const idToken = makeUnsignedToken({
      sub: sub(normalised),
      email: normalised,
      email_verified: true,
      'cognito:groups': normalised.includes('admin') ? [ADMIN_GROUP] : [],
      exp: Math.floor(Date.now() / 1000) + TOKEN_TTL_SECONDS,
      iat: Math.floor(Date.now() / 1000),
    });
    storage.setItem(MOCK_SESSION_KEY, normalised);
    return { idToken, user: userFromIdToken(idToken)! };
  }

  let current: Session | null = null;

  function requireEmail(email: string) {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      throw new AuthError('invalid_credentials', 'Enter a valid email address.');
    }
  }

  return {
    async getSession() {
      const email = storage.getItem(MOCK_SESSION_KEY);
      if (!email) return null;
      const claims = current ? parseJwtClaims(current.idToken) : null;
      if (!current || !claims || isExpired(claims) || current.user.email !== email) {
        current = issue(email);
      }
      return current;
    },
    async signIn(email, password) {
      await wait();
      requireEmail(email);
      if (!password) throw new AuthError('invalid_credentials', 'Enter your password.');
      current = issue(email);
      return current;
    },
    async signUp(email, password) {
      await wait();
      requireEmail(email);
      if (password.length < 8) throw new AuthError('invalid_password', 'Password must be at least 8 characters.');
    },
    async confirmSignUp(_email, code) {
      await wait();
      if (!/^\d{6}$/.test(code.trim())) throw new AuthError('invalid_code', 'Enter the 6-digit code (any 6 digits in demo mode).');
    },
    async resendCode() {
      await wait();
    },
    async forgotPassword(email) {
      await wait();
      requireEmail(email);
    },
    async confirmForgotPassword(_email, code, newPassword) {
      await wait();
      if (!/^\d{6}$/.test(code.trim())) throw new AuthError('invalid_code', 'Enter the 6-digit code (any 6 digits in demo mode).');
      if (newPassword.length < 8) throw new AuthError('invalid_password', 'Password must be at least 8 characters.');
    },
    async signOut() {
      current = null;
      storage.removeItem(MOCK_SESSION_KEY);
    },
    async deleteUser() {
      await wait();
      current = null;
      storage.removeItem(MOCK_SESSION_KEY);
    },
  };
}
