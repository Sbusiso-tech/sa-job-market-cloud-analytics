import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserAttribute,
  CognitoUserPool,
  type CognitoUserSession,
} from 'amazon-cognito-identity-js';
import { AuthError, type AuthService, type Session } from './service';
import { userFromIdToken } from './tokens';

export interface CognitoConfig {
  userPoolId: string;
  userPoolClientId: string;
}

function normaliseEmail(email: string): string {
  return email.trim().toLowerCase();
}

/** Maps Cognito exception names to friendly, non-revealing messages. */
export function toAuthError(err: unknown): AuthError {
  const e = (err ?? {}) as { code?: string; name?: string; message?: string };
  const code = e.code ?? e.name ?? '';
  switch (code) {
    case 'UserNotConfirmedException':
      return new AuthError('not_confirmed', 'Your email address is not confirmed yet.');
    case 'NotAuthorizedException':
    case 'UserNotFoundException':
      return new AuthError('invalid_credentials', 'Incorrect email or password.');
    case 'UsernameExistsException':
      return new AuthError('user_exists', 'An account with this email already exists.');
    case 'InvalidPasswordException':
      return new AuthError(
        'invalid_password',
        e.message?.replace(/^Password does not conform to policy: /, '') ||
          'Password does not meet the requirements.',
      );
    case 'CodeMismatchException':
      return new AuthError('invalid_code', 'That code is not correct.');
    case 'ExpiredCodeException':
      return new AuthError('expired_code', 'That code has expired. Request a new one.');
    case 'LimitExceededException':
    case 'TooManyRequestsException':
    case 'TooManyFailedAttemptsException':
      return new AuthError('too_many_attempts', 'Too many attempts. Please wait a moment and try again.');
    case 'InvalidParameterException':
      return new AuthError('unknown', e.message || 'Some details are not valid.');
    default:
      return new AuthError('unknown', 'Something went wrong. Please try again.');
  }
}

function toSession(session: CognitoUserSession): Session {
  const idToken = session.getIdToken().getJwtToken();
  const user = userFromIdToken(idToken);
  if (!user) throw new AuthError('unknown', 'Received an invalid ID token.');
  return { idToken, user };
}

export function createCognitoAuth(config: CognitoConfig): AuthService {
  if (!config.userPoolId || !config.userPoolClientId) {
    const notConfigured = () =>
      Promise.reject(new AuthError('not_configured', 'Sign-in is not configured for this deployment.'));
    return {
      getSession: () => Promise.resolve(null),
      signIn: notConfigured,
      signUp: notConfigured,
      confirmSignUp: notConfigured,
      resendCode: notConfigured,
      forgotPassword: notConfigured,
      confirmForgotPassword: notConfigured,
      signOut: () => Promise.resolve(),
      deleteUser: notConfigured,
    };
  }

  const pool = new CognitoUserPool({ UserPoolId: config.userPoolId, ClientId: config.userPoolClientId });
  const userFor = (email: string) => new CognitoUser({ Username: normaliseEmail(email), Pool: pool });

  function currentSession(): Promise<{ user: CognitoUser; session: CognitoUserSession } | null> {
    const user = pool.getCurrentUser();
    if (!user) return Promise.resolve(null);
    return new Promise((resolve) => {
      // getSession refreshes the tokens with the refresh token when they have expired.
      user.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session || !session.isValid()) resolve(null);
        else resolve({ user, session });
      });
    });
  }

  return {
    async getSession() {
      const current = await currentSession();
      return current ? toSession(current.session) : null;
    },

    signIn(email, password) {
      const user = userFor(email);
      const details = new AuthenticationDetails({ Username: normaliseEmail(email), Password: password });
      return new Promise<Session>((resolve, reject) => {
        user.authenticateUser(details, {
          onSuccess: (session) => {
            try {
              resolve(toSession(session));
            } catch (err) {
              reject(err instanceof AuthError ? err : toAuthError(err));
            }
          },
          onFailure: (err) => reject(toAuthError(err)),
          newPasswordRequired: () =>
            reject(
              new AuthError(
                'new_password_required',
                'This account needs a new password. Use "Forgot password" to set one.',
              ),
            ),
          mfaRequired: () => reject(new AuthError('unknown', 'MFA is not supported by this app.')),
          totpRequired: () => reject(new AuthError('unknown', 'MFA is not supported by this app.')),
        });
      });
    },

    signUp(email, password) {
      const attributes = [new CognitoUserAttribute({ Name: 'email', Value: normaliseEmail(email) })];
      return new Promise<void>((resolve, reject) => {
        pool.signUp(normaliseEmail(email), password, attributes, [], (err) => {
          if (err) reject(toAuthError(err));
          else resolve();
        });
      });
    },

    confirmSignUp(email, code) {
      return new Promise<void>((resolve, reject) => {
        userFor(email).confirmRegistration(code.trim(), true, (err: unknown) => {
          if (err) reject(toAuthError(err));
          else resolve();
        });
      });
    },

    resendCode(email) {
      return new Promise<void>((resolve, reject) => {
        userFor(email).resendConfirmationCode((err) => {
          if (err) reject(toAuthError(err));
          else resolve();
        });
      });
    },

    forgotPassword(email) {
      return new Promise<void>((resolve, reject) => {
        userFor(email).forgotPassword({
          onSuccess: () => resolve(),
          onFailure: (err) => reject(toAuthError(err)),
          inputVerificationCode: () => resolve(),
        });
      });
    },

    confirmForgotPassword(email, code, newPassword) {
      return new Promise<void>((resolve, reject) => {
        userFor(email).confirmPassword(code.trim(), newPassword, {
          onSuccess: () => resolve(),
          onFailure: (err) => reject(toAuthError(err)),
        });
      });
    },

    async signOut() {
      pool.getCurrentUser()?.signOut();
    },

    async deleteUser() {
      const current = await currentSession();
      if (!current) throw new AuthError('invalid_credentials', 'Your session has expired. Sign in again.');
      await new Promise<void>((resolve, reject) => {
        current.user.deleteUser((err) => {
          if (err) reject(toAuthError(err));
          else resolve();
        });
      });
      current.user.signOut();
    },
  };
}
