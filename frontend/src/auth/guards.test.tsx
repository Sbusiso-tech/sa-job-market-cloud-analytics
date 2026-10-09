import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/utils';

describe('route guards', () => {
  it('RequireAdmin sends signed-out visitors to sign in', async () => {
    renderApp({ route: '/admin' });
    expect(await screen.findByRole('heading', { level: 1, name: /sign in/i })).toBeInTheDocument();
  });

  it('RequireAdmin redirects signed-in non-admins to the dashboard', async () => {
    renderApp({ route: '/admin', signedInAs: 'member@example.com' });
    expect(await screen.findByText(/only for administrators/i)).toBeInTheDocument();
    expect(await screen.findByRole('heading', { level: 1, name: /south african tech job market/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
  });

  it('RequireAdmin lets admins in', async () => {
    renderApp({ route: '/admin', signedInAs: 'admin@example.com' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Admin' })).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /run pipeline now/i })).toBeInTheDocument();
    expect(await screen.findByText(/dead-letter queue is empty/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Admin' })).toBeInTheDocument();
  });

  it('RequireAuth sends signed-out visitors to sign in and back afterwards', async () => {
    const { user } = renderApp({ route: '/saved' });
    expect(await screen.findByRole('heading', { level: 1, name: /sign in/i })).toBeInTheDocument();
    await user.type(screen.getByLabelText(/email/i), 'naledi@example.com');
    await user.type(screen.getByLabelText(/^password/i), 'whatever');
    await user.click(screen.getByRole('button', { name: /^sign in$/i }));
    expect(await screen.findByRole('heading', { level: 1, name: /saved jobs/i })).toBeInTheDocument();
  });
});
