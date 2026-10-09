import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderApp } from '../test/utils';

function jobLinks() {
  return screen.getAllByRole('link').filter((a) => a.getAttribute('href')?.startsWith('/jobs/'));
}

describe('Jobs', () => {
  it('loads more jobs with next_cursor until there are none left', async () => {
    const { user } = renderApp({ route: '/jobs' });

    expect(await screen.findByText('Showing 20 jobs')).toBeInTheDocument();
    expect(jobLinks()).toHaveLength(20);

    await user.click(screen.getByRole('button', { name: /load more/i }));
    expect(await screen.findByText('Showing 40 jobs')).toBeInTheDocument();
    expect(jobLinks()).toHaveLength(40);
    expect(new Set(jobLinks().map((a) => a.getAttribute('href'))).size).toBe(40);
    expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument();
  });

  it('filters by province and skill from the skill list', async () => {
    const { user } = renderApp({ route: '/jobs' });
    await screen.findByText('Showing 20 jobs');

    await user.selectOptions(screen.getByLabelText('Province'), 'Gauteng');
    await waitFor(() => expect(screen.getByText(/in Gauteng$/)).toBeInTheDocument());

    await waitFor(() => expect(screen.getByLabelText('Skill')).toBeEnabled());
    await user.selectOptions(screen.getByLabelText('Skill'), 'SQL');
    const status = await screen.findByText(/in Gauteng asking for SQL|No jobs match/);
    expect(status).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /clear filters/i }));
    expect(await screen.findByText('Showing 20 jobs')).toBeInTheDocument();
  });

  it('applies filters from the URL', async () => {
    renderApp({ route: '/jobs?province=Remote' });
    expect(await screen.findByText(/in Remote$/)).toBeInTheDocument();
    expect(screen.getByLabelText('Province')).toHaveValue('Remote');
  });
});
