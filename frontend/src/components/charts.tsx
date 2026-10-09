import type { ReactNode } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { SalaryStat, SkillStat, TrendWeek } from '../api/types';
import { formatNumber, formatPercent, formatSignedChange, formatZar, formatZarCompact } from '../lib/format';

export const PALETTE = {
  green: '#007A4D',
  greenLight: '#7cc4a4',
  gold: '#FFB612',
  blue: '#002395',
  red: '#DE3831',
  ink: '#1b2430',
  teal: '#0e7c86',
  grid: '#e6e9ef',
  muted: '#5b6675',
};

const LINE_COLOURS = [PALETTE.green, PALETTE.blue, PALETTE.gold, PALETTE.red, PALETTE.teal];
const INITIAL = { width: 640, height: 320 };

function ChartFrame({ label, height, children, table }: { label: string; height: number; children: ReactNode; table: ReactNode }) {
  return (
    <figure className="chart" aria-label={label}>
      <div className="chart__canvas" style={{ height }} aria-hidden="true">
        {children}
      </div>
      <details className="chart__table">
        <summary>Show data as a table</summary>
        <div className="table-wrap">{table}</div>
      </details>
    </figure>
  );
}

interface TooltipEntry {
  payload?: unknown;
}

function TooltipBox({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className="chart-tooltip">
      <strong>{title}</strong>
      <dl>
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function TopSkillsChart({ skills, limit = 15 }: { skills: SkillStat[]; limit?: number }) {
  const data = skills.slice(0, limit);
  return (
    <ChartFrame
      label={`Bar chart of the top ${data.length} skills by number of job postings`}
      height={Math.max(260, data.length * 28 + 40)}
      table={
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Skill</th>
              <th scope="col">Category</th>
              <th scope="col" className="num">Jobs</th>
              <th scope="col" className="num">Share</th>
              <th scope="col" className="num">Change vs last week</th>
            </tr>
          </thead>
          <tbody>
            {skills.map((s) => (
              <tr key={s.skill}>
                <th scope="row">{s.skill}</th>
                <td>{s.category}</td>
                <td className="num">{formatNumber(s.count)}</td>
                <td className="num">{formatPercent(s.share)}</td>
                <td className="num">{formatSignedChange(s.change_vs_prev_week)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={INITIAL}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 48, bottom: 4, left: 8 }}>
          <CartesianGrid horizontal={false} stroke={PALETTE.grid} />
          <XAxis type="number" tick={{ fill: PALETTE.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="skill" width={110} tick={{ fill: PALETTE.ink, fontSize: 13 }} axisLine={false} tickLine={false} interval={0} />
          <Tooltip
            cursor={{ fill: 'rgba(0, 122, 77, 0.06)' }}
            content={({ active, payload }) => {
              const s = (payload?.[0] as TooltipEntry | undefined)?.payload as SkillStat | undefined;
              if (!active || !s) return null;
              return (
                <TooltipBox
                  title={s.skill}
                  rows={[
                    ['Jobs', formatNumber(s.count)],
                    ['Share of jobs', formatPercent(s.share)],
                    ['vs last week', formatSignedChange(s.change_vs_prev_week)],
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="count" radius={[0, 6, 6, 0]} maxBarSize={22}>
            {data.map((s, i) => (
              <Cell key={s.skill} fill={i < 3 ? PALETTE.green : PALETTE.greenLight} />
            ))}
            <LabelList dataKey="count" position="right" fill={PALETTE.ink} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

interface SalaryRow extends SalaryStat {
  base: number;
  lower: number;
  upper: number;
}

export function SalaryRangesChart({ salaries }: { salaries: SalaryStat[] }) {
  const data: SalaryRow[] = [...salaries]
    .sort((a, b) => b.median - a.median)
    .map((s) => ({ ...s, base: s.p25, lower: s.median - s.p25, upper: s.p75 - s.median }));
  return (
    <ChartFrame
      label="Salary ranges per skill: 25th percentile, median and 75th percentile in rand per year"
      height={Math.max(260, data.length * 30 + 50)}
      table={
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Skill</th>
              <th scope="col" className="num">25th percentile</th>
              <th scope="col" className="num">Median</th>
              <th scope="col" className="num">75th percentile</th>
              <th scope="col" className="num">Sample</th>
            </tr>
          </thead>
          <tbody>
            {data.map((s) => (
              <tr key={s.skill}>
                <th scope="row">{s.skill}</th>
                <td className="num">{formatZar(s.p25)}</td>
                <td className="num">{formatZar(s.median)}</td>
                <td className="num">{formatZar(s.p75)}</td>
                <td className="num">{formatNumber(s.sample_size)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={INITIAL}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
          <CartesianGrid horizontal={false} stroke={PALETTE.grid} />
          <XAxis
            type="number"
            tickFormatter={(v: number) => formatZarCompact(v)}
            tick={{ fill: PALETTE.muted, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis type="category" dataKey="skill" width={100} tick={{ fill: PALETTE.ink, fontSize: 13 }} axisLine={false} tickLine={false} interval={0} />
          <Tooltip
            cursor={{ fill: 'rgba(0, 35, 149, 0.05)' }}
            content={({ active, payload }) => {
              const s = (payload?.[0] as TooltipEntry | undefined)?.payload as SalaryRow | undefined;
              if (!active || !s) return null;
              return (
                <TooltipBox
                  title={`${s.skill} (${s.sample_size} salaries)`}
                  rows={[
                    ['75th percentile', formatZar(s.p75)],
                    ['Median', formatZar(s.median)],
                    ['25th percentile', formatZar(s.p25)],
                  ]}
                />
              );
            }}
          />
          <Bar dataKey="base" stackId="range" fill="transparent" isAnimationActive={false} />
          <Bar dataKey="lower" stackId="range" fill={PALETTE.gold} maxBarSize={18} name="25th percentile to median" />
          <Bar dataKey="upper" stackId="range" fill={PALETTE.green} maxBarSize={18} radius={[0, 6, 6, 0]} name="Median to 75th percentile" />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function TrendsChart({ weeks, topN = 5 }: { weeks: TrendWeek[]; topN?: number }) {
  const latest = weeks[weeks.length - 1];
  const skills = (latest?.top_skills ?? []).slice(0, topN).map((s) => s.skill);
  const rows = weeks.map((w) => {
    const row: Record<string, string | number | null> = { week: w.week.replace(/^\d{4}-/, '') };
    for (const skill of skills) row[skill] = w.top_skills.find((s) => s.skill === skill)?.count ?? null;
    return row;
  });
  return (
    <ChartFrame
      label={`Line chart of weekly job counts for the top ${skills.length} skills over ${weeks.length} weeks`}
      height={300}
      table={
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Week</th>
              <th scope="col" className="num">All jobs</th>
              {skills.map((s) => (
                <th scope="col" className="num" key={s}>
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map((w) => (
              <tr key={w.week}>
                <th scope="row">{w.week}</th>
                <td className="num">{formatNumber(w.total_jobs)}</td>
                {skills.map((s) => (
                  <td className="num" key={s}>
                    {formatNumber(w.top_skills.find((x) => x.skill === s)?.count ?? null)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={INITIAL}>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid stroke={PALETTE.grid} vertical={false} />
          <XAxis dataKey="week" tick={{ fill: PALETTE.muted, fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: PALETTE.muted, fontSize: 12 }} axisLine={false} tickLine={false} width={40} />
          <Tooltip contentStyle={{ borderRadius: 10, border: `1px solid ${PALETTE.grid}` }} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 13 }} />
          {skills.map((skill, i) => (
            <Line
              key={skill}
              type="monotone"
              dataKey={skill}
              stroke={LINE_COLOURS[i % LINE_COLOURS.length]}
              strokeWidth={2.5}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
