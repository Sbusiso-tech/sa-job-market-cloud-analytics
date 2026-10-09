import { describe, expect, it } from 'vitest';
import { groupsFromClaims, isExpired, makeUnsignedToken, parseJwtClaims, userFromIdToken } from './tokens';

describe('token claims', () => {
  it('reads sub, email and cognito:groups from an ID token', () => {
    const token = makeUnsignedToken({ sub: 'abc-123', email: 'thandi@example.co.za', 'cognito:groups': ['admins'] });
    expect(userFromIdToken(token)).toEqual({
      sub: 'abc-123',
      email: 'thandi@example.co.za',
      groups: ['admins'],
      isAdmin: true,
    });
  });

  it('treats a user without groups as a normal member', () => {
    const user = userFromIdToken(makeUnsignedToken({ sub: 'u1', email: 'a@example.com' }));
    expect(user?.groups).toEqual([]);
    expect(user?.isAdmin).toBe(false);
  });

  it('is not fooled by a group that merely contains the word admin', () => {
    const user = userFromIdToken(makeUnsignedToken({ sub: 'u1', 'cognito:groups': ['not-admins', 'editors'] }));
    expect(user?.isAdmin).toBe(false);
  });

  it('decodes base64url payloads with non-ASCII characters', () => {
    const token = makeUnsignedToken({ sub: 'u2', email: 'sipho.ndlovu+thembé@example.com' });
    expect(parseJwtClaims(token)?.email).toBe('sipho.ndlovu+thembé@example.com');
  });

  it('accepts groups flattened to a string', () => {
    expect(groupsFromClaims({ sub: 'x', 'cognito:groups': 'admins editors' as unknown as string[] })).toEqual([
      'admins',
      'editors',
    ]);
  });

  it.each(['', 'not-a-jwt', 'a.b', 'a.!!!.c', `x.${btoa('{"email":"no-sub"}')}.y`])('rejects malformed token %j', (token) => {
    expect(parseJwtClaims(token)).toBeNull();
    expect(userFromIdToken(token)).toBeNull();
  });

  it('detects expiry with clock skew', () => {
    const now = Date.UTC(2026, 9, 9, 8, 0, 0);
    expect(isExpired({ sub: 'x', exp: now / 1000 + 3600 }, now)).toBe(false);
    expect(isExpired({ sub: 'x', exp: now / 1000 + 10 }, now)).toBe(true);
    expect(isExpired({ sub: 'x', exp: now / 1000 - 1 }, now, 0)).toBe(true);
    expect(isExpired({ sub: 'x' }, now)).toBe(false);
  });
});
