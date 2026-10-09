import type { AuthUser } from './tokens';

export interface Session {
  idToken: string;
  user: AuthUser;
}

export type AuthErrorCode =
  | 'not_confirmed'
  | 'invalid_credentials'
  | 'user_exists'
  | 'invalid_password'
  | 'invalid_code'
  | 'expired_code'
  | 'too_many_attempts'
  | 'new_password_required'
  | 'not_configured'
  | 'unknown';

export class AuthError extends Error {
  readonly code: AuthErrorCode;
  constructor(code: AuthErrorCode, message: string) {
    super(message);
    this.name = 'AuthError';
    this.code = code;
  }
}

/** Everything the UI needs from Cognito. Implemented by Cognito (real) and an offline mock. */
export interface AuthService {
  /** The current session, refreshed with the refresh token when the ID token has expired. */
  getSession(): Promise<Session | null>;
  signIn(email: string, password: string): Promise<Session>;
  signUp(email: string, password: string): Promise<void>;
  confirmSignUp(email: string, code: string): Promise<void>;
  resendCode(email: string): Promise<void>;
  forgotPassword(email: string): Promise<void>;
  confirmForgotPassword(email: string, code: string, newPassword: string): Promise<void>;
  signOut(): Promise<void>;
  deleteUser(): Promise<void>;
}
