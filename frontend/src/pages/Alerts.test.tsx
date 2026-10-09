import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ApiError } from '../api/client';
import { MAX_ALERTS } from '../api/types';
import { renderApp } from '../test/utils';

describe('Alerts', () => {
  it('creates an alert and explains the pending SNS confirmation', async () => {
    const { user } = renderApp({ route: '/alerts', signedInAs: 'lerato@example.co.za' });

    expect(await screen.findByText(/how alerts work/i)).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: 'Python' }));
    await user.click(screen.getByRole('button', { name: 'AWS' }));
    await user.selectOptions(screen.getByLabelText(/province/i), 'Western Cape');
    await user.click(screen.getByRole('button', { name: /create alert/i }));

    expect(await screen.findByText(/confirm your email to start receiving alerts/i)).toBeInTheDocument();
    expect(screen.getByText(/check your inbox/i)).toHaveTextContent(/click the AWS confirmation link/i);
    expect(screen.getByText('lerato@example.co.za')).toBeInTheDocument();

    const list = screen.getByRole('list', { name: 'Your alerts' });
    expect(within(list).getByText('Python')).toBeInTheDocument();
    expect(within(list).getByText(/western cape/i)).toBeInTheDocument();
    expect(screen.getByText(`1 of ${MAX_ALERTS} used`)).toBeInTheDocument();
  });

  it('allows at most 5 skills per alert', async () => {
    const { user } = renderApp({ route: '/alerts', signedInAs: 'skills@example.com' });
    for (const name of ['Python', 'Java', 'C#', 'SQL', 'AWS']) {
      await user.click(await screen.findByRole('button', { name }));
    }
    expect(screen.getByText(/5 of 5 selected/i)).toHaveTextContent(/maximum reached/i);
    expect(screen.getByRole('button', { name: 'Azure' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Python', pressed: true })).toBeEnabled();
  });

  it('hides the form once the user has 5 alerts', async () => {
    const email = 'busy@example.com';
    const { api, unmount } = renderApp({ route: '/alerts', signedInAs: email });
    await screen.findByText(/how alerts work/i);
    for (let i = 0; i < MAX_ALERTS; i++) await api.createAlert({ skills: ['SQL'] });
    unmount();

    // Re-render with the same in-memory server state by reusing the api client.
    renderApp({ route: '/alerts', signedInAs: email, apiOverrides: api });
    expect(await screen.findByText(/alert limit reached/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /create alert/i })).not.toBeInTheDocument();
    expect(screen.getByText(`${MAX_ALERTS} of ${MAX_ALERTS} used`)).toBeInTheDocument();
  });

  it('shows a clear message when the server answers limit_reached', async () => {
    const { user } = renderApp({
      route: '/alerts',
      signedInAs: 'race@example.com',
      apiOverrides: {
        createAlert: async () => {
          throw new ApiError(409, 'limit_reached', 'You can have at most 5 alerts');
        },
      },
    });
    await user.click(await screen.findByRole('button', { name: 'Excel' }));
    await user.click(screen.getByRole('button', { name: /create alert/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/already have 5 alerts/i);
  });
});
