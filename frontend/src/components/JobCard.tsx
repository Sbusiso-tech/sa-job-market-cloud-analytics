import { Link } from 'react-router-dom';
import type { Job } from '../api/types';
import { employmentLabel, formatRelative, formatSalaryRange, seniorityLabel } from '../lib/format';
import { SkillChip } from './ui';

export function JobCard({ job, highlightSkill }: { job: Job; highlightSkill?: string }) {
  const salary = formatSalaryRange(job.salary_min_zar, job.salary_max_zar);
  const lowerSkill = highlightSkill?.toLowerCase();
  return (
    <article className="job-card">
      <div className="job-card__main">
        <h2 className="job-card__title">
          <Link to={`/jobs/${encodeURIComponent(job.job_id)}`}>{job.title}</Link>
        </h2>
        <p className="job-card__meta">
          {job.company && <span>{job.company}</span>}
          {job.company && job.location && <span aria-hidden="true">·</span>}
          {job.location && <span>{job.location}</span>}
          {job.province !== 'Unknown' && job.province !== 'Remote' && (
            <span className="badge badge--outline">{job.province}</span>
          )}
          {job.is_remote && <span className="badge badge--blue">Remote</span>}
        </p>
        <div className="chip-row">
          {job.skills.map((s) => (
            <SkillChip key={s} tone={s.toLowerCase() === lowerSkill ? 'accent' : 'default'}>
              {s}
            </SkillChip>
          ))}
        </div>
      </div>
      <div className="job-card__side">
        <span className={salary ? 'job-card__salary' : 'job-card__salary job-card__salary--none'}>
          {salary ?? 'Salary not given'}
          {salary && job.salary_is_predicted && <span className="badge badge--gold">estimate</span>}
        </span>
        <span className="job-card__tags">
          {seniorityLabel(job.seniority)} · {employmentLabel(job.employment_type)}
        </span>
        {job.date_posted && (
          <time className="job-card__date" dateTime={job.date_posted}>
            {formatRelative(job.date_posted)}
          </time>
        )}
      </div>
    </article>
  );
}
