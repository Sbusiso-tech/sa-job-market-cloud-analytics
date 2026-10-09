import { useCallback } from 'react';
import { Link } from 'react-router-dom';
import type { NameCount, Overview, ProvinceStat, SkillPair, SkillStat } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { SalaryRangesChart, TopSkillsChart, TrendsChart } from '../components/charts';
import { EmptyState, ErrorView, Loading } from '../components/StatusViews';
import { AsyncBlock, Card, PageHeader, SkillChip, StatCard } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import {
  employmentLabel,
  formatDateTime,
  formatNumber,
  formatRelative,
  formatSignedChange,
  formatZar,
  seniorityLabel,
} from '../lib/format';
import { useApi } from '../services';

function isEmptyOverview(o: Overview): boolean {
  return o.total_jobs === 0;
}

function Movers({ skills }: { skills: SkillStat[] }) {
  const sorted = [...skills].sort((a, b) => b.change_vs_prev_week - a.change_vs_prev_week);
  const rising = sorted.filter((s) => s.change_vs_prev_week > 0).slice(0, 3);
  const falling = sorted.filter((s) => s.change_vs_prev_week < 0).reverse().slice(0, 3);
  if (rising.length === 0 && falling.length === 0) return null;
  return (
    <div className="movers">
      <div>
        <h3 className="movers__title">Rising this week</h3>
        <ul className="movers__list">
          {rising.map((s) => (
            <li key={s.skill}>
              <span>{s.skill}</span>
              <span className="trend trend--up">
                <span aria-hidden="true">▲</span> {formatSignedChange(s.change_vs_prev_week)}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="movers__title">Cooling off</h3>
        <ul className="movers__list">
          {falling.map((s) => (
            <li key={s.skill}>
              <span>{s.skill}</span>
              <span className="trend trend--down">
                <span aria-hidden="true">▼</span> {formatSignedChange(s.change_vs_prev_week)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ProvincesTable({ provinces }: { provinces: ProvinceStat[] }) {
  const max = Math.max(1, ...provinces.map((p) => p.count));
  return (
    <div className="table-wrap">
      <table className="table table--provinces">
        <caption className="visually-hidden">Jobs, median salary and top skills per province</caption>
        <thead>
          <tr>
            <th scope="col">Province</th>
            <th scope="col">Jobs</th>
            <th scope="col" className="num">Median salary</th>
            <th scope="col">Top skills</th>
          </tr>
        </thead>
        <tbody>
          {provinces.map((p) => (
            <tr key={p.province}>
              <th scope="row">
                <Link to={`/jobs?province=${encodeURIComponent(p.province)}`}>{p.province}</Link>
              </th>
              <td>
                <div className="inline-bar">
                  <span className="inline-bar__fill" style={{ width: `${(p.count / max) * 100}%` }} aria-hidden="true" />
                  <span className="inline-bar__value">{formatNumber(p.count)}</span>
                </div>
              </td>
              <td className="num">{formatZar(p.median_salary_zar)}</td>
              <td>
                <div className="chip-row">
                  {p.top_skills.map((s) => (
                    <SkillChip key={s.skill}>{s.skill}</SkillChip>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SkillPairs({ pairs }: { pairs: SkillPair[] }) {
  const top = pairs.slice(0, 10);
  const max = Math.max(1, ...top.map((p) => p.count));
  return (
    <ol className="bar-list">
      {top.map((p) => (
        <li key={p.skills.join('+')} className="bar-list__item">
          <div className="bar-list__label">
            <span>
              {p.skills[0]} <span className="muted">+</span> {p.skills[1]}
            </span>
            <span className="bar-list__value">{formatNumber(p.count)} jobs</span>
          </div>
          <span className="bar-list__track" aria-hidden="true">
            <span className="bar-list__fill bar-list__fill--blue" style={{ width: `${(p.count / max) * 100}%` }} />
          </span>
        </li>
      ))}
    </ol>
  );
}

function Breakdown<N extends string>({ title, items, label }: { title: string; items: NameCount<N>[]; label: (n: N) => string }) {
  const total = items.reduce((sum, i) => sum + i.count, 0) || 1;
  return (
    <div className="breakdown">
      <h3 className="breakdown__title">{title}</h3>
      <ul className="bar-list">
        {items.map((i) => {
          const pct = Math.round((i.count / total) * 100);
          return (
            <li key={i.name} className="bar-list__item">
              <div className="bar-list__label">
                <span>{label(i.name)}</span>
                <span className="bar-list__value">
                  {formatNumber(i.count)} <span className="muted">({pct}%)</span>
                </span>
              </div>
              <span className="bar-list__track" aria-hidden="true">
                <span className="bar-list__fill bar-list__fill--gold" style={{ width: `${pct}%` }} />
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function EmptyDashboard() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader title="South African tech job market" />
      <EmptyState title="No data yet">
        <p>
          The data pipeline has not run yet. It collects South African job postings every day at 05:00 SAST, works
          out the skills, salaries and provinces, and the dashboard fills up straight after.
        </p>
        {user?.isAdmin ? (
          <p>
            <Link className="btn btn--primary" to="/admin">
              Run the pipeline now
            </Link>
          </p>
        ) : (
          <p>Please check back tomorrow morning.</p>
        )}
      </EmptyState>
    </>
  );
}

export default function Dashboard() {
  const api = useApi();
  const overview = useAsync(useCallback(() => api.getOverview(), [api]));
  const skills = useAsync(useCallback(() => api.getSkills(), [api]));
  const salaries = useAsync(useCallback(() => api.getSalaries(), [api]));
  const provinces = useAsync(useCallback(() => api.getProvinces(), [api]));
  const pairs = useAsync(useCallback(() => api.getSkillPairs(), [api]));
  const trends = useAsync(useCallback(() => api.getTrends(), [api]));

  const o = overview.data;
  if (!o) {
    if (overview.error) return <ErrorView error={overview.error} onRetry={overview.reload} title="Could not load the dashboard" />;
    return <Loading label="Loading the latest market data…" />;
  }
  if (isEmptyOverview(o)) return <EmptyDashboard />;

  return (
    <div className="dashboard">
      <PageHeader
        title="South African tech job market"
        subtitle={
          <>
            Which skills employers want, what they pay and where the jobs are, based on postings from the last{' '}
            {o.window_days} days.{' '}
            <span className="updated" title={formatDateTime(o.last_updated)}>
              Last updated {formatRelative(o.last_updated)}.
            </span>
          </>
        }
        actions={
          <Link to="/jobs" className="btn btn--primary">
            Browse jobs
          </Link>
        }
      />

      <section className="stat-grid" aria-label="Headline numbers">
        <StatCard label={`Jobs (last ${o.window_days} days)`} value={formatNumber(o.total_jobs)} accent="green" />
        <StatCard label="New this week" value={formatNumber(o.new_this_week)} accent="blue" />
        <StatCard label="Median salary" value={formatZar(o.median_salary_zar)} hint="per year" accent="gold" />
        <StatCard label="Top skill" value={o.top_skill ?? '—'} accent="red" />
        <StatCard label="Top province" value={o.top_province ?? '—'} accent="green" />
      </section>

      <div className="grid grid--2">
        <Card title="Most in-demand skills" subtitle="Job postings that mention each skill, with the change against last week">
          <AsyncBlock state={skills} isEmpty={(d) => d.skills.length === 0} emptyText="No skills recorded yet.">
            {(d) => (
              <>
                <TopSkillsChart skills={d.skills} />
                <Movers skills={d.skills} />
              </>
            )}
          </AsyncBlock>
        </Card>
        <Card title="Salary ranges by skill" subtitle="Rand per year: 25th percentile, median and 75th percentile">
          <AsyncBlock
            state={salaries}
            isEmpty={(d) => d.salaries.length === 0}
            emptyText="Not enough postings with salaries yet (at least 5 per skill)."
          >
            {(d) => (
              <>
                <SalaryRangesChart salaries={d.salaries} />
                <p className="legend-note">
                  <span className="swatch swatch--gold" aria-hidden="true" /> 25th percentile to median
                  <span className="swatch swatch--green" aria-hidden="true" /> median to 75th percentile
                </p>
              </>
            )}
          </AsyncBlock>
        </Card>
      </div>

      <Card title="Jobs by province" subtitle="Where the jobs are, what they pay and which skills lead">
        <AsyncBlock state={provinces} isEmpty={(d) => d.provinces.length === 0}>
          {(d) => <ProvincesTable provinces={d.provinces} />}
        </AsyncBlock>
      </Card>

      <Card title="Weekly trends" subtitle="Postings per week for this week's top five skills">
        <AsyncBlock state={trends} isEmpty={(d) => d.weeks.length === 0} emptyText="Trends appear after the first weekly snapshot.">
          {(d) => <TrendsChart weeks={d.weeks} />}
        </AsyncBlock>
      </Card>

      <div className="grid grid--2">
        <Card title="Skills that go together" subtitle="Most common pairs in the same job posting">
          <AsyncBlock state={pairs} isEmpty={(d) => d.pairs.length === 0}>
            {(d) => <SkillPairs pairs={d.pairs} />}
          </AsyncBlock>
        </Card>
        <Card title="Seniority and employment type">
          <div className="breakdowns">
            {o.seniority.length > 0 && <Breakdown title="Seniority" items={o.seniority} label={seniorityLabel} />}
            {o.employment_type.length > 0 && (
              <Breakdown title="Employment type" items={o.employment_type} label={employmentLabel} />
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
