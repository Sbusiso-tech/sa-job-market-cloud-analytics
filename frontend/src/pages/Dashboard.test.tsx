import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { Overview } from '../api/types';
import { renderApp } from '../test/utils';

describe('Dashboard', () => {
  it('renders headline numbers, charts and tables from mock data', async () => {
    renderApp({ route: '/' });

    expect(await screen.findByRole('heading', { level: 1, name: /south african tech job market/i })).toBeInTheDocument();
    const headline = screen.getByRole('region', { name: /headline numbers/i });
    expect(within(headline).getByText(/1\s240/)).toBeInTheDocument();
    expect(within(headline).getByText(/R\s?560\s000/)).toBeInTheDocument();
    expect(within(headline).getByText('SQL')).toBeInTheDocument();
    expect(screen.getByText(/last updated/i)).toBeInTheDocument();

    expect(await screen.findByRole('figure', { name: /top 15 skills/i })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: /rising this week/i })).toBeInTheDocument();
    expect(await screen.findByRole('figure', { name: /salary ranges per skill/i })).toBeInTheDocument();
    expect(await screen.findByRole('figure', { name: /weekly job counts for the top 5 skills over 8 weeks/i })).toBeInTheDocument();

    const provinces = await screen.findByRole('table', { name: /top skills per province/i });
    expect(within(provinces).getByRole('link', { name: 'Gauteng' })).toHaveAttribute('href', '/jobs?province=Gauteng');
    expect(within(provinces).getByText(/R\s?590\s000/)).toBeInTheDocument();

    expect(await screen.findByText('Mid-level')).toBeInTheDocument();
    expect(screen.getByText('Full-time')).toBeInTheDocument();
    expect(await screen.findByText(/168 jobs/)).toBeInTheDocument();
  });

  it('shows a friendly empty state before the first pipeline run', async () => {
    const empty: Overview = {
      last_updated: null,
      window_days: 30,
      total_jobs: 0,
      new_this_week: 0,
      median_salary_zar: null,
      top_skill: null,
      top_province: null,
      seniority: [],
      employment_type: [],
    };
    renderApp({ route: '/', apiOverrides: { getOverview: async () => empty } });
    expect(await screen.findByRole('heading', { name: /no data yet/i })).toBeInTheDocument();
    expect(screen.getByText(/pipeline has not run yet/i)).toBeInTheDocument();
  });

  it('shows an error with a retry button when the API fails', async () => {
    renderApp({
      route: '/',
      apiOverrides: {
        getOverview: async () => {
          throw new Error('Service unavailable');
        },
      },
    });
    expect(await screen.findByRole('alert')).toHaveTextContent(/service unavailable/i);
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});
