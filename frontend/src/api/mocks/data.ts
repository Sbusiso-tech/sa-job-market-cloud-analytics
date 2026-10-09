// FAKE demo data for offline mode. Company names are invented; numbers are plausible but not real.
import type {
  EmploymentType,
  Job,
  Overview,
  PipelineRun,
  Province,
  ProvinceStat,
  SalaryStat,
  Seniority,
  SkillListItem,
  SkillPair,
  SkillStat,
  TrendWeek,
} from '../types';

const DAY_MS = 86_400_000;

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function pick<T>(rand: () => number, items: readonly T[]): T {
  return items[Math.floor(rand() * items.length)] as T;
}

function roundTo(value: number, step: number): number {
  return Math.round(value / step) * step;
}

export function isoWeek(date: Date): string {
  const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const week = Math.ceil(((d.getTime() - yearStart.getTime()) / DAY_MS + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

export const SKILL_LIST: SkillListItem[] = [
  { name: 'Python', category: 'Programming Language' },
  { name: 'Java', category: 'Programming Language' },
  { name: 'C#', category: 'Programming Language' },
  { name: 'JavaScript', category: 'Programming Language' },
  { name: 'TypeScript', category: 'Programming Language' },
  { name: 'SAP ABAP', category: 'Enterprise Platform' },
  { name: 'REST APIs', category: 'Web & Application Framework' },
  { name: 'SQL', category: 'Programming Language' },
  { name: 'PostgreSQL', category: 'Database' },
  { name: 'SQL Server', category: 'Database' },
  { name: 'MongoDB', category: 'Database' },
  { name: 'AWS', category: 'Cloud Platform' },
  { name: 'Azure', category: 'Cloud Platform' },
  { name: 'GCP', category: 'Cloud Platform' },
  { name: 'Docker', category: 'DevOps & Infrastructure' },
  { name: 'Kubernetes', category: 'DevOps & Infrastructure' },
  { name: 'Terraform', category: 'DevOps & Infrastructure' },
  { name: 'CI/CD', category: 'DevOps & Infrastructure' },
  { name: 'Linux', category: 'DevOps & Infrastructure' },
  { name: 'React', category: 'Web & Application Framework' },
  { name: 'Angular', category: 'Web & Application Framework' },
  { name: 'Node.js', category: 'Web & Application Framework' },
  { name: '.NET', category: 'Web & Application Framework' },
  { name: 'Spring Boot', category: 'Web & Application Framework' },
  { name: 'Apache Spark', category: 'Data Engineering' },
  { name: 'Power BI', category: 'Analytics & BI' },
  { name: 'Excel', category: 'Analytics & BI' },
  { name: 'Machine Learning', category: 'Machine Learning & AI' },
  { name: 'SAP', category: 'Enterprise Platform' },
  { name: 'Salesforce', category: 'Enterprise Platform' },
  { name: 'Sage Pastel', category: 'Accounting & ERP Software' },
  { name: 'Syspro', category: 'Accounting & ERP Software' },
  { name: 'ITIL', category: 'IT Service Management & Certification' },
  { name: 'CCNA', category: 'IT Service Management & Certification' },
  { name: 'CompTIA', category: 'IT Service Management & Certification' },
  { name: 'Agile', category: 'Ways of Working' },
  { name: 'Git', category: 'DevOps & Infrastructure' },
];

const CATEGORY = new Map(SKILL_LIST.map((s) => [s.name, s.category]));

interface Role {
  title: string;
  skills: string[];
}

const ROLES: Role[] = [
  { title: 'Data Engineer', skills: ['Python', 'SQL', 'AWS', 'Apache Spark'] },
  { title: 'Data Analyst', skills: ['SQL', 'Power BI', 'Excel', 'Python'] },
  { title: '.NET Developer', skills: ['C#', '.NET', 'SQL Server', 'Azure'] },
  { title: 'Java Developer', skills: ['Java', 'Spring Boot', 'SQL', 'Docker'] },
  { title: 'Frontend Developer', skills: ['React', 'TypeScript', 'JavaScript', 'Git'] },
  { title: 'Full Stack Developer', skills: ['React', 'Node.js', 'TypeScript', 'AWS', 'PostgreSQL'] },
  { title: 'Cloud Engineer', skills: ['AWS', 'Terraform', 'Docker', 'Linux'] },
  { title: 'DevOps Engineer', skills: ['Azure', 'Kubernetes', 'Docker', 'CI/CD', 'Linux'] },
  { title: 'SAP ABAP Consultant', skills: ['SAP', 'SAP ABAP', 'SQL'] },
  { title: 'Business Analyst', skills: ['SQL', 'Excel', 'Power BI', 'Agile'] },
  { title: 'BI Developer', skills: ['Power BI', 'SQL', 'Azure', 'Excel'] },
  { title: 'IT Support Technician', skills: ['ITIL', 'CCNA', 'Excel'] },
  { title: 'Cyber Security Analyst', skills: ['CompTIA', 'Azure', 'Linux', 'CCNA'] },
  { title: 'Machine Learning Engineer', skills: ['Python', 'Machine Learning', 'AWS', 'SQL'] },
  { title: 'Salesforce Developer', skills: ['Salesforce', 'REST APIs', 'JavaScript'] },
  { title: 'ERP Systems Analyst', skills: ['Syspro', 'Sage Pastel', 'SQL', 'Excel'] },
];

const COMPANIES = [
  'Karoo Bank',
  'Umoya Insurance',
  'Protea Retail Group',
  'Highveld Logistics',
  'Fynbos Digital',
  'Baobab Health',
  'Ubuntu Telecom',
  'Kalahari Fintech',
  'Indlovu Consulting',
  'Jacaranda Software',
  'Drakensberg Energy',
  'Mzansi Media House',
];

const PLACES: { province: Province; city: string | null; location: string; weight: number }[] = [
  { province: 'Gauteng', city: 'Sandton', location: 'Sandton, Johannesburg', weight: 5 },
  { province: 'Gauteng', city: 'Johannesburg', location: 'Johannesburg CBD', weight: 3 },
  { province: 'Gauteng', city: 'Pretoria', location: 'Pretoria East, Pretoria', weight: 3 },
  { province: 'Gauteng', city: 'Midrand', location: 'Midrand', weight: 2 },
  { province: 'Gauteng', city: 'Centurion', location: 'Centurion', weight: 2 },
  { province: 'Western Cape', city: 'Cape Town', location: 'Cape Town CBD', weight: 6 },
  { province: 'Western Cape', city: 'Stellenbosch', location: 'Stellenbosch', weight: 2 },
  { province: 'Western Cape', city: 'Bellville', location: 'Bellville, Cape Town', weight: 2 },
  { province: 'KwaZulu-Natal', city: 'Durban', location: 'Durban', weight: 3 },
  { province: 'KwaZulu-Natal', city: 'Umhlanga', location: 'Umhlanga Rocks', weight: 2 },
  { province: 'Eastern Cape', city: 'Gqeberha', location: 'Gqeberha', weight: 2 },
  { province: 'Eastern Cape', city: 'East London', location: 'East London', weight: 1 },
  { province: 'Free State', city: 'Bloemfontein', location: 'Bloemfontein', weight: 1 },
  { province: 'Limpopo', city: 'Polokwane', location: 'Polokwane', weight: 1 },
  { province: 'Mpumalanga', city: 'Mbombela', location: 'Mbombela', weight: 1 },
  { province: 'North West', city: 'Rustenburg', location: 'Rustenburg', weight: 1 },
  { province: 'Remote', city: null, location: 'Remote (South Africa)', weight: 3 },
];

const LEVELS: { prefix: string; seniority: Seniority; band: [number, number]; years: [number, number | null] }[] = [
  { prefix: 'Junior', seniority: 'junior', band: [300_000, 460_000], years: [0, 2] },
  { prefix: 'Intermediate', seniority: 'mid', band: [450_000, 720_000], years: [3, 5] },
  { prefix: 'Senior', seniority: 'senior', band: [700_000, 1_080_000], years: [5, null] },
  { prefix: 'Lead', seniority: 'lead', band: [950_000, 1_400_000], years: [8, null] },
];

const EMPLOYMENT: EmploymentType[] = ['full_time', 'full_time', 'full_time', 'full_time', 'contract', 'contract'];

function weightedPlace(rand: () => number) {
  const total = PLACES.reduce((sum, p) => sum + p.weight, 0);
  let roll = rand() * total;
  for (const place of PLACES) {
    roll -= place.weight;
    if (roll <= 0) return place;
  }
  return PLACES[0]!;
}

function makeJobs(now: number): Job[] {
  const rand = mulberry32(2026);
  const jobs: Job[] = [];
  for (let i = 0; i < 40; i++) {
    const role = pick(rand, ROLES);
    const level = pick(rand, LEVELS);
    const place = weightedPlace(rand);
    const company = pick(rand, COMPANIES);
    const [low, high] = level.band;
    const hasSalary = rand() > 0.2;
    const min = roundTo(low + rand() * (high - low) * 0.6, 10_000);
    const max = roundTo(min + 60_000 + rand() * 180_000, 10_000);
    const employment = role.title.includes('Support') && rand() > 0.5 ? 'temporary' : pick(rand, EMPLOYMENT);
    const posted = new Date(now - Math.floor(rand() * 14 * DAY_MS));
    posted.setUTCMinutes(0, 0, 0);
    const skills = role.skills.filter((_, idx) => idx < 3 || rand() > 0.3);
    const title = `${level.prefix} ${role.title}`;
    jobs.push({
      job_id: `mock-${(i + 1).toString(16).padStart(4, '0')}${Math.floor(rand() * 0xffffff).toString(16)}`,
      title,
      company,
      location: place.location,
      city: place.city,
      province: place.province,
      is_remote: place.province === 'Remote',
      salary_min_zar: hasSalary ? min : null,
      salary_max_zar: hasSalary ? Math.min(max, 1_400_000) : null,
      salary_is_predicted: hasSalary && rand() > 0.75,
      seniority: level.seniority,
      employment_type: employment,
      experience_years_min: level.years[0],
      experience_years_max: level.years[1],
      skills,
      date_posted: posted.toISOString().replace('.000Z', 'Z'),
      url: `https://www.adzuna.co.za/details/demo-${i + 1}`,
      source: 'adzuna',
      description_snippet:
        `${company} is looking for a ${title.toLowerCase()} to join a friendly team in ` +
        `${place.city ?? 'a remote-first setup'}. You will work with ${skills.join(', ')} ` +
        `and help us deliver reliable products for customers across South Africa…`,
    });
  }
  return jobs.sort((a, b) => (b.date_posted ?? '').localeCompare(a.date_posted ?? ''));
}

const TOTAL_JOBS = 1240;

const SKILL_COUNTS: [string, number, number][] = [
  ['SQL', 412, 14],
  ['Excel', 356, -6],
  ['Python', 318, 21],
  ['Power BI', 241, 9],
  ['Azure', 228, 11],
  ['AWS', 214, 17],
  ['C#', 172, -3],
  ['Java', 158, 2],
  ['SAP', 151, -8],
  ['.NET', 146, 4],
  ['JavaScript', 139, 5],
  ['React', 121, 12],
  ['Agile', 117, 0],
  ['ITIL', 104, -2],
  ['Docker', 96, 7],
  ['Linux', 92, 3],
  ['CCNA', 88, -4],
  ['TypeScript', 84, 9],
  ['Kubernetes', 71, 6],
  ['Git', 69, 1],
  ['SQL Server', 66, -1],
  ['Salesforce', 58, 3],
  ['CompTIA', 55, 5],
  ['Apache Spark', 47, 4],
  ['Node.js', 45, 2],
  ['Terraform', 41, 5],
  ['Machine Learning', 39, 6],
  ['Sage Pastel', 36, -2],
  ['PostgreSQL', 33, 1],
  ['Angular', 30, -3],
];

const SALARY_ROWS: [string, number, number, number, number][] = [
  ['Python', 64, 480_000, 680_000, 920_000],
  ['SQL', 92, 420_000, 590_000, 820_000],
  ['AWS', 41, 600_000, 840_000, 1_120_000],
  ['Azure', 44, 560_000, 780_000, 1_040_000],
  ['SAP', 28, 620_000, 900_000, 1_250_000],
  ['Power BI', 39, 400_000, 540_000, 720_000],
  ['Excel', 71, 300_000, 420_000, 580_000],
  ['Java', 31, 520_000, 720_000, 980_000],
  ['C#', 35, 480_000, 660_000, 880_000],
  ['React', 23, 450_000, 640_000, 860_000],
  ['Kubernetes', 14, 700_000, 960_000, 1_280_000],
  ['Salesforce', 11, 580_000, 820_000, 1_060_000],
];

const PROVINCE_ROWS: [Province, number, number | null, [string, number][]][] = [
  ['Gauteng', 610, 590_000, [['SQL', 205], ['Excel', 168], ['Python', 151], ['Azure', 118], ['SAP', 92]]],
  ['Western Cape', 312, 620_000, [['Python', 102], ['SQL', 98], ['AWS', 81], ['React', 54], ['TypeScript', 41]]],
  ['KwaZulu-Natal', 128, 470_000, [['Excel', 46], ['SQL', 39], ['SAP', 22], ['C#', 18], ['Power BI', 17]]],
  ['Eastern Cape', 54, 430_000, [['Excel', 21], ['SQL', 17], ['SAP', 11], ['Java', 7], ['Power BI', 6]]],
  ['Remote', 48, 780_000, [['AWS', 22], ['Python', 21], ['React', 17], ['TypeScript', 15], ['Docker', 12]]],
  ['Free State', 26, 410_000, [['Excel', 11], ['SQL', 8], ['ITIL', 6], ['CCNA', 5], ['Sage Pastel', 4]]],
  ['Mpumalanga', 18, 450_000, [['SAP', 8], ['Excel', 7], ['SQL', 5], ['CCNA', 3], ['Linux', 2]]],
  ['Limpopo', 16, 390_000, [['Excel', 7], ['ITIL', 5], ['CCNA', 4], ['SQL', 4], ['Sage Pastel', 2]]],
  ['North West', 14, 420_000, [['SAP', 6], ['Excel', 6], ['SQL', 3], ['Linux', 2], ['CCNA', 2]]],
  ['Unknown', 8, null, [['Excel', 3], ['SQL', 2]]],
  ['Northern Cape', 6, null, [['Excel', 3], ['SAP', 2], ['SQL', 1]]],
];

const PAIR_ROWS: [string, string, number][] = [
  ['Python', 'SQL', 168],
  ['Excel', 'SQL', 151],
  ['Power BI', 'SQL', 137],
  ['Excel', 'Power BI', 118],
  ['.NET', 'C#', 112],
  ['AWS', 'Python', 97],
  ['Azure', 'C#', 74],
  ['JavaScript', 'React', 71],
  ['Docker', 'Kubernetes', 63],
  ['Azure', 'SQL', 60],
  ['React', 'TypeScript', 58],
  ['Java', 'SQL', 55],
  ['SAP', 'SQL', 49],
  ['AWS', 'Docker', 44],
  ['Excel', 'SAP', 41],
  ['CCNA', 'Linux', 38],
  ['Docker', 'Linux', 35],
  ['Apache Spark', 'Python', 33],
  ['AWS', 'Terraform', 31],
  ['Agile', 'Java', 29],
];

const TREND_SKILLS: [string, number, number][] = [
  ['SQL', 82, 1.6],
  ['Excel', 74, 0.6],
  ['Python', 55, 2.4],
  ['Power BI', 44, 1.1],
  ['Azure', 41, 1.3],
  ['AWS', 36, 1.9],
  ['C#', 34, 0.2],
  ['Java', 31, 0.1],
];

export interface MockDataset {
  jobs: Job[];
  overview: Overview;
  skills: SkillStat[];
  salaries: SalaryStat[];
  provinces: ProvinceStat[];
  pairs: SkillPair[];
  trends: TrendWeek[];
  runs: PipelineRun[];
}

export function buildDataset(nowMs: number = Date.now()): MockDataset {
  const today = new Date(nowMs);
  const lastUpdated = new Date(
    Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate(), 3, 12),
  );
  if (lastUpdated.getTime() > nowMs) lastUpdated.setUTCDate(lastUpdated.getUTCDate() - 1);
  const lastUpdatedIso = lastUpdated.toISOString().replace('.000Z', 'Z');

  const rand = mulberry32(41);
  const trends: TrendWeek[] = [];
  for (let w = 7; w >= 0; w--) {
    const weekDate = new Date(nowMs - w * 7 * DAY_MS);
    const step = 7 - w;
    const topSkills = TREND_SKILLS.map(([skill, base, growth]) => ({
      skill,
      count: Math.round(base + growth * step * 2 + (rand() - 0.5) * 8),
    })).sort((a, b) => b.count - a.count);
    trends.push({
      week: isoWeek(weekDate),
      total_jobs: Math.round(255 + step * 9 + (rand() - 0.5) * 30),
      top_skills: topSkills,
    });
  }

  const runs: PipelineRun[] = [];
  for (let d = 0; d < 8; d++) {
    const start = new Date(lastUpdated.getTime() - d * DAY_MS - 12 * 60_000);
    const failed = d === 4;
    runs.push({
      execution_id: `daily-${start.toISOString().slice(0, 10).replace(/-/g, '')}T030000Z`,
      status: failed ? 'FAILED' : 'SUCCEEDED',
      started_at: start.toISOString().replace('.000Z', 'Z'),
      stopped_at: new Date(start.getTime() + (failed ? 4 : 11) * 60_000).toISOString().replace('.000Z', 'Z'),
      fetched: failed ? 120 : 340 + Math.round(rand() * 60),
      new_jobs: failed ? 0 : 70 + Math.round(rand() * 50),
      failed: failed ? 120 : Math.round(rand() * 2),
    });
  }

  return {
    jobs: makeJobs(nowMs),
    overview: {
      last_updated: lastUpdatedIso,
      window_days: 30,
      total_jobs: TOTAL_JOBS,
      new_this_week: 214,
      median_salary_zar: 560_000,
      top_skill: 'SQL',
      top_province: 'Gauteng',
      seniority: [
        { name: 'mid', count: 420 },
        { name: 'senior', count: 380 },
        { name: 'junior', count: 210 },
        { name: 'lead', count: 110 },
        { name: 'unspecified', count: 80 },
        { name: 'intern', count: 40 },
      ],
      employment_type: [
        { name: 'full_time', count: 900 },
        { name: 'contract', count: 230 },
        { name: 'internship', count: 45 },
        { name: 'part_time', count: 25 },
        { name: 'temporary', count: 20 },
        { name: 'unspecified', count: 20 },
      ],
    },
    skills: SKILL_COUNTS.map(([skill, count, change]) => ({
      skill,
      category: CATEGORY.get(skill) ?? 'Other',
      count,
      share: Math.round((count / TOTAL_JOBS) * 1000) / 1000,
      change_vs_prev_week: change,
    })),
    salaries: SALARY_ROWS.map(([skill, sample_size, p25, median, p75]) => ({
      skill,
      sample_size,
      p25,
      median,
      p75,
    })),
    provinces: PROVINCE_ROWS.map(([province, count, median, top]) => ({
      province,
      count,
      median_salary_zar: median,
      top_skills: top.map(([skill, c]) => ({ skill, count: c })),
    })),
    pairs: PAIR_ROWS.map(([a, b, count]) => ({ skills: [a, b], count })),
    trends,
    runs,
  };
}
