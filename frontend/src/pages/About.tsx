import { Card, PageHeader } from '../components/ui';
import { GITHUB_URL } from '../lib/constants';

const ARCHITECTURE: [string, string][] = [
  ['Collect', 'EventBridge Scheduler starts a Step Functions pipeline every day at 05:00 SAST. An ingest Lambda calls the Adzuna South Africa API and queues one SQS message per job.'],
  ['Process', 'A Lambda cleans each posting, extracts skills, converts salaries to rand per year and maps the location to a province. Failures land in a dead-letter queue.'],
  ['Aggregate', 'Statistics (top skills, salary ranges, provinces, skill pairs, weekly trends) are precomputed into small DynamoDB items, so every dashboard request is one cheap read.'],
  ['Serve', 'This React app lives in a private S3 bucket behind CloudFront. The same CloudFront distribution routes /api/* to an API Gateway HTTP API backed by Lambda.'],
  ['Secure', 'Cognito handles sign-up and sign-in; API Gateway checks the JWT and admin routes require the admins group. Each Lambda has its own least-privilege IAM role.'],
  ['Notify', 'A DynamoDB Stream triggers an alert matcher that emails each subscriber one digest through SNS. CloudWatch alarms email the operator about failures.'],
];

export default function About() {
  return (
    <div className="narrow">
      <PageHeader
        title="About this project"
        subtitle="A serverless AWS analytics platform for the South African tech job market."
      />
      <Card title="What it does">
        <p>
          Every day the platform collects South African job postings, works out which tech skills employers ask for,
          what they pay in rand per year and where the jobs are by province. Anyone can explore the dashboard and job
          list; signed-in users can save jobs and get email alerts such as “new jobs in Gauteng that ask for Python”.
        </p>
        <p>
          It was built as a cloud computing capstone with two hard rules: everything is infrastructure as code (AWS
          SAM), and it costs nothing to run because it only uses always-free AWS services and stays inside their limits.
        </p>
      </Card>
      <Card title="Architecture">
        <ol className="arch-list">
          {ARCHITECTURE.map(([step, text], i) => (
            <li key={step}>
              <span className="arch-list__num" aria-hidden="true">
                {i + 1}
              </span>
              <div>
                <strong>{step}</strong>
                <p>{text}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className="tech-stack">
          <strong>Stack:</strong> Python 3.12 Lambdas, DynamoDB, S3, SQS, SNS, Step Functions, EventBridge, API Gateway,
          Cognito, CloudFront, AWS SAM, GitHub Actions (OIDC) and React with TypeScript.
        </p>
      </Card>
      <Card title="Source code">
        <p>
          The full source, including the SAM templates and tests, is on GitHub:{' '}
          <a href={GITHUB_URL} target="_blank" rel="noopener noreferrer">
            Sbusiso-tech/sa-job-market-cloud-analytics
            <span className="visually-hidden"> (opens in a new tab)</span>
          </a>
          .
        </p>
        <p className="hint">Job data comes from the Adzuna API. Salary figures marked “estimate” are Adzuna’s predictions.</p>
      </Card>
    </div>
  );
}
