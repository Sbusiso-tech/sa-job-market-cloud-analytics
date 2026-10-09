export interface IdTokenClaims {
  sub: string;
  email?: string;
  exp?: number;
  'cognito:groups'?: string[];
  [claim: string]: unknown;
}

export interface AuthUser {
  sub: string;
  email: string;
  groups: string[];
  isAdmin: boolean;
}

export const ADMIN_GROUP = 'admins';

function base64UrlDecode(segment: string): string {
  const base64 = segment.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
  const binary = atob(padded);
  const bytes = Uint8Array.from(binary, (ch) => ch.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function base64UrlEncode(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Decodes (does not verify) a JWT payload. Verification is API Gateway's job. */
export function parseJwtClaims(token: string): IdTokenClaims | null {
  const parts = token.split('.');
  if (parts.length !== 3 || !parts[1]) return null;
  try {
    const claims: unknown = JSON.parse(base64UrlDecode(parts[1]));
    if (typeof claims !== 'object' || claims === null) return null;
    const record = claims as Record<string, unknown>;
    if (typeof record.sub !== 'string') return null;
    return record as IdTokenClaims;
  } catch {
    return null;
  }
}

export function groupsFromClaims(claims: IdTokenClaims): string[] {
  const raw = claims['cognito:groups'];
  if (Array.isArray(raw)) return raw.filter((g): g is string => typeof g === 'string');
  // Some proxies flatten the array to a space or comma separated string.
  if (typeof raw === 'string') return (raw as string).split(/[\s,]+/).filter(Boolean);
  return [];
}

export function userFromIdToken(token: string): AuthUser | null {
  const claims = parseJwtClaims(token);
  if (!claims) return null;
  const groups = groupsFromClaims(claims);
  return {
    sub: claims.sub,
    email: typeof claims.email === 'string' ? claims.email : '',
    groups,
    isAdmin: groups.includes(ADMIN_GROUP),
  };
}

export function isExpired(claims: IdTokenClaims, nowMs: number = Date.now(), skewSeconds = 30): boolean {
  if (typeof claims.exp !== 'number') return false;
  return claims.exp - skewSeconds <= nowMs / 1000;
}

/** Builds an unsigned JWT-shaped token. Only used by the offline mock mode and tests. */
export function makeUnsignedToken(claims: IdTokenClaims): string {
  const header = base64UrlEncode(JSON.stringify({ alg: 'none', typ: 'JWT' }));
  return `${header}.${base64UrlEncode(JSON.stringify(claims))}.mock-signature`;
}
