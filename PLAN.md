# SA Job Market Cloud Analytics Platform: Project Plan

A serverless AWS platform that collects South African job postings every day, works out which
skills, salaries and provinces are in demand, and serves the results through a secure web app.
Signed-in users can save jobs and subscribe to email alerts such as *"new Data Engineer jobs in
Gauteng that ask for Python"*.

It reuses the data logic of the existing **Job Market Intelligence Platform** (source connectors,
skill taxonomy, salary and experience parsing) and rebuilds the infrastructure as a serverless,
**zero-cost** AWS application that satisfies the Cloud Computing capstone deliverables.

---

## 1. Goals

1. Meet every capstone deliverable (section 2) with a real, working feature, not a placeholder.
2. **Cost nothing to run.** Only always-free AWS services or usage that stays inside free limits.
   Anything that bills by the hour is banned (section 4).
3. Be portfolio-ready: one-command deploy and teardown, a clear README, architecture diagram,
   screenshots, tests and a CI/CD pipeline.
4. Be about South Africa: SA job data, rand (ZAR) salaries, the 9 provinces, local skills.

## 2. Capstone deliverables and how they are met

| Deliverable | How this project meets it |
|---|---|
| Authenticated backend API: **API Gateway** | HTTP API with routes under `/api/*`, a Cognito JWT authorizer and throttling |
| Authenticated backend API: **Lambda** | Python 3.12 (arm64) functions for ingestion, processing, aggregation, the API and alert matching |
| Authenticated backend API: **DynamoDB** | Single-table design: jobs, statistics, saved jobs, alerts (section 7) |
| Authenticated backend API: **Cognito** | User pool with email sign-up, `admins` group, JWTs checked by API Gateway |
| **All infrastructure as Code** | AWS SAM (CloudFormation) templates. `sam deploy` builds everything and `sam delete` removes it |
| **Web app on S3 + CloudFront** | React dashboard in a private S3 bucket, served only through CloudFront (Origin Access Control) |
| **Asynchronous services** | EventBridge Scheduler → Step Functions → SQS (with dead-letter queue) → Lambda. DynamoDB Streams → alert matcher |
| **Notifications** | SNS emails to users when new jobs match their alerts. CloudWatch alarms email the admin on failures |
| **Secure access control** | Cognito user/admin roles, least-privilege IAM per function, private encrypted S3, secrets in SSM Parameter Store, HTTPS only, API throttling |
| Demo week | Live demo script, README, retrospective (section 13) |

## 3. Architecture

```
                         ┌──────────────────────── AWS (eu-west-1) ────────────────────────┐
 EventBridge Scheduler   │                                                                 │
   (daily 05:00 SAST) ───┼─► Step Functions "pipeline"                                     │
                         │     1. Ingest Lambda ── Adzuna API (za) ──► S3 raw/            │
                         │            └─ one message per job ──► SQS jobs-queue ──► DLQ    │
                         │     2. Wait until queue is empty (poll loop)                    │
                         │            SQS ──► Process Lambda: clean, skills, salary ZAR,   │
                         │                     province ──► DynamoDB JOB items + S3 curated/│
                         │     3. Aggregate Lambda ── S3 curated/ ──► DynamoDB STATS items │
                         │     4. Publish run summary (SNS admin topic, on failure only)   │
                         │                                                                 │
                         │  DynamoDB Stream (new JOB items) ──► Alert Matcher Lambda       │
                         │                                    └─► SNS "job-alerts" email   │
                         │                                                                 │
 Browser ──HTTPS──► CloudFront ──┬── /*      ──► S3 (React build, private, OAC)           │
                         │       └── /api/*  ──► API Gateway HTTP API ──► API Lambdas      │
                         │                         └─ JWT authorizer ◄── Cognito user pool │
                         └─────────────────────────────────────────────────────────────────┘
```

Design choices:

- **The API sits behind CloudFront at `/api/*`.** The site and the API share one origin, so CORS
  isn't needed. Public statistics are cached at the edge, which saves API Gateway and Lambda
  calls. Personal (`/api/me/*`) and admin routes are never cached.
- **Statistics are precomputed** once per pipeline run and stored as small DynamoDB items, so
  each dashboard request is a single cheap `GetItem`. No query engine is needed.
- **No runtime dependencies.** Lambda code uses only the Python standard library plus `boto3`
  (already in the Lambda runtime). `requests`, `pydantic` and `PyYAML` from the old project are
  replaced by `urllib`, `dataclasses` and JSON, so there are no layers or container builds.

## 4. Zero-cost rules

### Allowed services and the free limits we design within

| Service | Free allowance | Our expected use |
|---|---|---|
| Lambda | 1M requests + 400k GB-s / month (always free) | well under 10k requests |
| DynamoDB | 25 GB, 25 RCU, 25 WCU provisioned (always free) | under 50 MB, **20 RCU / 20 WCU total** |
| DynamoDB Streams | Reads by Lambda triggers are free | — |
| SQS | 1M requests / month (always free) | ~30k |
| SNS | 1,000 email deliveries / month (always free) | under 200 |
| Step Functions (Standard) | 4,000 state transitions / month (always free) | ~600 |
| EventBridge Scheduler | 14M invocations / month (always free) | 30 |
| Cognito | 10,000 monthly active users (Lite tier) | a handful |
| CloudFront | 1 TB transfer + 10M requests / month (always free) | tiny |
| CloudWatch | 10 alarms, 5 GB logs, 10 custom metrics (always free) | ≤ 6 alarms, 7-day log retention |
| SSM Parameter Store | Standard parameters are free | 2 parameters |
| KMS | AWS-managed keys and 20k requests / month free | AWS-managed keys only |
| CloudFormation / SAM | free | — |
| AWS Budgets | 2 budgets free | 2 budgets |
| API Gateway (HTTP API) | 1M calls / month for 12 months, or covered by Free-plan credits | under 10k |
| S3 | 5 GB + 20k GET / 2k PUT for 12 months, or covered by Free-plan credits | under 100 MB, ~200 PUTs |

### Banned (these cost money)

NAT Gateway, Lambdas inside a VPC, RDS / Aurora, ECS Fargate, ECR, EC2, Athena, Glue, Kinesis,
Secrets Manager, customer-managed KMS keys, Route 53 domains/hosted zones, DynamoDB on-demand
mode, DynamoDB auto scaling (it creates CloudWatch alarms), X-Ray, WAF, SES outside the sandbox.

### Guardrails

- Use a **new AWS account on the Free plan** (accounts created since July 2025). The Free plan
  can't bill you: it uses credits, then pauses the account. An AWS Educate account also works,
  if it allows creating IAM roles and Cognito pools.
- Region **eu-west-1 (Ireland)**: every service we need, standard prices, reasonable latency to SA.
- Two **AWS Budgets** (in IaC, optional parameter): a zero-spend budget and a $1 monthly budget,
  both emailing the owner.
- A tag on every resource (`project=sa-jobmarket`) and **7-day log retention** on every log group.
- **S3 lifecycle**: `raw/` expires after 30 days, `curated/` after 90 days.
- DynamoDB **TTL** deletes job items 60 days after they were last seen (TTL deletes are free).
- API Gateway stage throttling (rate 10/s, burst 20) so abuse can't drive costs up.
- `make destroy` (`sam delete` + empty buckets) to remove everything after the demo.

## 5. Data source: Adzuna South Africa

- Endpoint `https://api.adzuna.com/v1/api/jobs/za/search/{page}` with a free app id and key.
- **Free key limits:** 25 calls/minute, 250/day, 1,000/week, 2,500/month.
  The daily run makes **8 search terms × up to 5 pages = at most 40 calls** (≤ 1,200/month), with
  a pause between calls to stay under the per-minute limit.
- Search terms (configurable): `software developer`, `data engineer`, `data analyst`,
  `cloud engineer`, `devops`, `cyber security`, `business analyst`, `IT support`.
- Keys are stored as SSM SecureString parameters `/sa-jobmarket/adzuna/app_id` and `.../app_key`,
  created once by hand (never committed, never in CloudFormation plain text).
- Offline mode: `backend/src/sajobs/sample_data/adzuna_za_sample.json` lets tests and demos run without keys.

## 6. Data processing (ported from the existing platform)

| Step | Source in old project | Change |
|---|---|---|
| Map Adzuna payload → job record | `sources/adzuna.py`, `models.py` | `pydantic` → `dataclasses`, `requests` → `urllib` |
| Strip HTML, normalise text | `transform.py` | unchanged logic |
| Skill extraction | `skills.py`, `skills_taxonomy.yml` | taxonomy → JSON; add SA skills: SAP, Sage/Pastel, Salesforce, Power BI, Excel, Syspro, etc. |
| Salary parsing / annualising | `transform.py` | report in **ZAR per year**; monthly ×12, hourly ×2,080 |
| Experience & seniority | `transform.py` | unchanged logic |
| **New:** province mapping | — | city/area → one of the 9 provinces (e.g. Sandton → Gauteng, Stellenbosch → Western Cape), else `Unknown` / `Remote` |
| De-duplication | Spark job | `job_id = sha1(source + source_id)` and conditional `PutItem` (only new jobs are inserted) |

Statistics computed by the Aggregate Lambda (last 30 days of curated data):

- **Overview**: total jobs, new this week, median salary, top skill, top province, last updated.
- **Skills**: top 30 skills with counts and the change against the previous week.
- **Salaries**: p25 / median / p75 ZAR per year for each skill with ≥ 5 salaried jobs.
- **Provinces**: jobs per province and the top 5 skills in each.
- **Skill pairs**: the most common skill combinations (e.g. Python + SQL).
- **Seniority & employment type** breakdowns.

## 7. DynamoDB design (single table `sa-jobmarket`)

Provisioned capacity: table **10 RCU / 10 WCU**, GSI1 and GSI2 **5 RCU / 5 WCU** each: 20/20
total, inside the 25/25 free allowance. Writes are spread out by the SQS trigger's
`MaximumConcurrency: 2` and retries with backoff on throttling.

| Entity | PK | SK | GSI1PK / GSI1SK | Notes |
|---|---|---|---|---|
| Job | `JOB#<job_id>` | `META` | `PROV#<province>` / `<date_posted>#<job_id>` | also `GSI2PK = JOBS`, `GSI2SK = <date_posted>#<job_id>` for the newest-first list of all jobs; title, company, location, skills, salary, url, `ttl` |
| Stats | `STATS#LATEST` | `OVERVIEW` \| `SKILLS` \| `SALARIES` \| `PROVINCES` \| `PAIRS` \| `TRENDS` | — | JSON blobs, each < 400 KB |
| Weekly snapshot | `STATS#<yyyy-Www>` | `SKILLS` | — | for trend lines |
| User profile | `USER#<sub>` | `PROFILE` | — | email, SNS subscription ARN, created_at |
| Saved job | `USER#<sub>` | `SAVED#<job_id>` | — | copy of title/company for fast listing |
| Alert | `USER#<sub>` | `ALERT#<alert_id>` | — | skills[], province, max 5 per user |
| Alert index | `ALERTIDX#<skill>` | `<sub>#<alert_id>` | — | lets the matcher find alerts for a job's skills |
| Pipeline run | `RUN#<execution_id>` | `META` | — | counts: fetched, new, failed, duration |

Stream: `NEW_IMAGE`, with a Lambda **event filter** so the matcher only sees `INSERT` events where
`PK` begins with `JOB#` (filtered events are not billed).

## 8. API (HTTP API, all routes under `/api`)

Exact request and response shapes are in [`docs/api-contract.md`](docs/api-contract.md).

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /api/public/overview` | none | headline numbers, seniority and employment-type breakdowns |
| `GET /api/public/skills` | none | top skills + weekly change |
| `GET /api/public/skill-list` | none | every known skill, for pickers |
| `GET /api/public/salaries?skill=` | none | ZAR salary ranges |
| `GET /api/public/provinces` | none | jobs and top skills per province |
| `GET /api/public/skill-pairs` | none | most common skill combinations |
| `GET /api/public/trends` | none | weekly snapshots (up to 12 weeks) |
| `GET /api/public/jobs?province=&skill=&cursor=` | none | latest jobs (GSI1 by province or GSI2 for all, paginated) |
| `GET /api/public/jobs/{job_id}` | none | one job |
| `GET /api/me/saved-jobs` | user | list saved jobs |
| `PUT /api/me/saved-jobs/{job_id}` | user | save a job |
| `DELETE /api/me/saved-jobs/{job_id}` | user | unsave |
| `GET /api/me/alerts` | user | list alerts |
| `POST /api/me/alerts` | user | create alert (skills, province); subscribes email to SNS on first alert |
| `DELETE /api/me/alerts/{alert_id}` | user | delete alert |
| `DELETE /api/me` | user | delete all my data and SNS subscription (POPIA-friendly) |
| `POST /api/admin/runs` | admin | start the pipeline now |
| `GET /api/admin/runs` | admin | recent runs, counts, DLQ depth |

- The JWT authorizer validates Cognito tokens. Admin Lambdas also check that the
  `cognito:groups` claim contains `admins`.
- Input validation on every write route; consistent JSON error shape
  `{"error": {"code": "...", "message": "..."}}`.
- Lambdas are grouped by audience: `PublicApiFn`, `MeApiFn`, `AdminApiFn`, each with its own IAM role.

## 9. Notifications

- **Job alerts (users):** one SNS topic `job-alerts`. When a user creates their first alert, the
  API subscribes their email with a **filter policy** `{"user_sub": ["<sub>"]}`; AWS sends a
  confirmation email they must click. The Alert Matcher groups matches per user per stream batch
  and publishes **one digest email** per user (title, company, province, salary, link).
- **Operations (admin):** topic `ops-alerts` subscribed to the owner's email. CloudWatch alarms:
  DLQ has messages, state machine execution failed, any Lambda error rate > 0 over 1 day,
  DynamoDB throttled requests. (4–6 alarms, inside the free 10.)

## 10. Security and access control

- **S3:** Block Public Access on, SSE-S3 encryption, bucket policy denies non-TLS requests; the web
  bucket can only be read by the CloudFront distribution (OAC).
- **CloudFront:** HTTPS redirect, security headers response policy (HSTS, CSP, X-Frame-Options).
  The web app gets a custom policy with a strict CSP (`script-src 'self'`, `connect-src` limited to the
  site and the region's Cognito endpoint); the API behaviours keep the managed SecurityHeadersPolicy.
  After each aggregate, `AggregateFn` invalidates `/api/public/*` (one path per run, inside the 1,000 free
  invalidation paths a month); its role may only call `cloudfront:CreateInvalidation` on this distribution.
- **Cognito:** email as username, verified email, strong password policy, `admins` group,
  short-lived access tokens (1 h), SRP sign-in from the web app (no client secret in the browser).
- **IAM:** one role per function, scoped to exact resources and actions. For example `MeApiFn`
  gets DynamoDB item read/write on the table and `sns:Subscribe`/`Unsubscribe` only, with no S3 or
  Step Functions access. Users only reach their own `USER#<sub>` items: the `sub` always comes
  from the verified JWT, never from the request, and tests check this.
- **Secrets:** Adzuna keys only in SSM SecureString; never logged.
- **API:** throttling, request size limits, validation, no stack traces in responses.
- **Privacy (POPIA):** only email and Cognito `sub` are stored about users; `DELETE /api/me`
  removes all user items and the SNS subscription.
- **CI/CD:** GitHub Actions authenticates to AWS with **OIDC** (short-lived role credentials, no
  stored access keys); the deploy role only trusts this repository's `main` branch and is limited
  to the project's stacks.

## 11. Repository layout

```
.
├── PLAN.md
├── README.md                     portfolio README (architecture, screenshots, how to run)
├── Makefile                      venv, test, lint, demo, build, deploy, outputs, run-pipeline, seed-secrets,
│                                 frontend-install/-build/-deploy, destroy
├── .github/workflows/ci.yml      lint, test, build; deploy on main
├── backend/
│   ├── src/                      Lambda CodeUri for every function (stdlib + boto3 only)
│   │   ├── sajobs/
│   │   │   ├── models.py         Job dataclass
│   │   │   ├── adzuna.py         Adzuna client (urllib, paced, retries, 40-call cap) + sample loader
│   │   │   ├── transform.py      cleaning, ZAR salary, experience, seniority, enrich()
│   │   │   ├── skills.py         skill extraction
│   │   │   ├── skills_taxonomy.json
│   │   │   ├── provinces.py      location → province
│   │   │   ├── aggregate.py      statistics (pure functions)
│   │   │   ├── repository.py     DynamoDB access (all key patterns live here)
│   │   │   ├── http.py           API response/validation/claims helpers
│   │   │   ├── aws.py            cached boto3 clients
│   │   │   └── sample_data/adzuna_za_sample.json   36 fake Adzuna-shaped SA jobs
│   │   └── handlers/
│   │       ├── ingest.py  process.py  aggregate.py  alert_matcher.py
│   │       ├── pipeline_status.py   Step Functions helper (queue depth, mark run)
│   │       └── api_public.py  api_me.py  api_admin.py
│   ├── scripts/                  demo_offline.py, empty_bucket.py (used by make destroy)
│   ├── tests/                    pytest + moto (DynamoDB, S3, SQS, SNS, SSM, Step Functions mocked)
│   ├── pyproject.toml            pytest + ruff config
│   └── requirements-dev.txt      pytest, pytest-cov, moto, boto3, ruff, cfn-lint
├── infra/
│   ├── template.yaml             main SAM stack (everything in section 3)
│   ├── statemachine/pipeline.asl.json
│   ├── bootstrap/github-oidc.yaml  one-off: OIDC provider + deploy role
│   └── samconfig.toml            stack name, region, capabilities, tags (nothing personal)
├── frontend/
│   ├── src/ pages: Dashboard, Jobs, JobDetail, Saved, Alerts, Admin, SignIn, SignUp
│   ├── public/config.json        written at deploy time (user pool id, client id)
│   └── package.json              React + Vite + TypeScript, Recharts, amazon-cognito-identity-js
└── docs/
    ├── architecture.png
    ├── cost.md                   free-tier usage table + proof (Billing screenshot)
    ├── demo-script.md
    └── retrospective.md
```

## 12. Build phases

Each phase ends with something that can be demonstrated. Tick items off as they are completed.

### Phase 0: Setup (½ day)
- [x] `git init`, `.gitignore`, GitHub repository, `README.md` skeleton.
- [x] AWS account on the Free plan (expires 28 Feb 2027), MFA on root, an admin IAM user for daily
      work. Do **not** enable AWS Organizations or IAM Identity Center: that upgrades the account
      to the paid plan.
- [x] Zero-spend budget emailing the account owner.
- [x] Install AWS CLI v2, SAM CLI, Python 3.12, Node LTS (22+).
- [x] CLI profile `sa-jobmarket` for `eu-west-1`, using an IAM user access key stored only in
      `~/.aws/credentials` (permissions 600).
- [x] Adzuna app id/key stored as SSM SecureString parameters under `/sa-jobmarket/adzuna/`.
- **Done when:** `aws sts get-caller-identity` and `sam --version` work.

### Phase 1: Core library, offline (2 days)
- [x] Port models, Adzuna client, transform, skills from the old project; remove third-party deps.
- [x] Add SA skills, ZAR salary handling and `provinces.py`.
- [x] `aggregate.py` producing all statistics from a list of jobs.
- [x] Unit tests with the sample data (target ≥ 85% coverage of `sajobs`).
- **Done when:** `make test` passes and a script prints SA top skills from the sample file.

Phases 2–5 are deployed to `eu-west-1` and running on real Adzuna data: the pipeline, public API,
CloudFront, sign-in and web app are verified live.

### Phase 2: Data pipeline on AWS (3 days)
- [x] SAM: S3 data bucket (lifecycle, encryption), SQS + DLQ, DynamoDB table + GSI1 + stream + TTL.
- [x] Ingest, Process and Aggregate Lambdas; Step Functions state machine; daily EventBridge schedule.
- [x] Ops SNS topic + CloudWatch alarms; log retention 7 days.
- **Done when:** a manual execution fills DynamoDB with SA jobs and `STATS#LATEST` items.

### Phase 3: Public API + CloudFront (2 days)
- [x] HTTP API, `PublicApiFn`, throttling.
- [x] Web bucket + CloudFront with `/api/*` behaviour (cached public routes, uncached others).
- **Done when:** `https://<id>.cloudfront.net/api/public/skills` returns live data.

### Phase 4: Auth, saved jobs, alerts, notifications (3 days)
- [x] Cognito user pool (Lite), app client, `admins` group, JWT authorizer.
- [x] `MeApiFn` (saved jobs, alerts, delete account) and `AdminApiFn` (start/list runs).
- [x] `job-alerts` topic, subscription with filter policy, Alert Matcher on the stream.
- **Done when:** a test user creates an alert, a pipeline run inserts a matching job, and the
  user receives one digest email.

### Phase 5: Web app (4 days)
- [x] Vite + React + TypeScript; sign up / sign in / sign out with Cognito (SRP).
- [x] Dashboard: overview cards, top-skills bar chart, salary ranges, province map/table, trends.
- [x] Jobs list with province/skill filters and pagination; job detail; save button.
- [x] Saved jobs, Alerts (create/delete, confirmation hint), Admin page (run now, run history).
- [x] Deploy: `npm run build`, write `config.json` from stack outputs, `aws s3 sync`, invalidate `/index.html`.
- **Done when:** the whole flow works from the CloudFront URL on desktop and mobile.

### Phase 6: CI/CD and guardrails (2 days)
- [x] `infra/bootstrap/github-oidc.yaml` deployed once.
- [ ] `.github/workflows/ci.yml` jobs: `lint` (ruff, eslint) → `test` (pytest, vitest) → `build`
      (sam build, npm build) → `deploy` (main branch only, `sam deploy` + frontend sync).
      GitHub Actions is free for public repos and has 2,000 free minutes/month for private ones.
- [ ] $1 monthly budget in IaC (the zero-spend budget already exists); tags everywhere;
      `make destroy` tested end-to-end.
- **Done when:** a merge to `main` deploys automatically with no stored AWS keys.

### Phase 7: Portfolio polish and demo (2 days)
- [ ] README: problem, architecture diagram, deliverables table, screenshots, tech stack,
      how to deploy, cost proof, lessons learned.
- [ ] `docs/demo-script.md` (section 13) and `docs/retrospective.md`.
- [ ] Short screen recording / GIF of the app for the portfolio.

Rough total: **~3 weeks** of part-time work.

## 13. Demo week script

1. **Problem (1 min):** which tech skills SA employers want, and what they pay.
2. **Architecture (2 min):** diagram; map each deliverable to a service.
3. **Live demo (5 min):** dashboard → filter jobs by province → sign up → save a job → create an
   alert → admin triggers a run → show Step Functions graph → alert email arrives.
4. **IaC & CI/CD (2 min):** `template.yaml` tour, a GitHub Actions run.
5. **Cost (1 min):** Billing dashboard at R0.00 and the free-tier table.
6. **Retrospective (2 min):** what was completed, what wasn't, challenges, what we enjoyed,
   suggested improvements.

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Adzuna rate limits or outage | ≤ 40 calls/day, backoff, sample-data fallback, DLQ for bad records |
| DynamoDB throttling at 10 WCU | SQS `MaximumConcurrency: 2`, batch writes with retries, conditional puts |
| New accounts have a Lambda concurrency limit of 10 | no reserved concurrency; SQS max concurrency instead |
| Users don't confirm SNS email subscription | UI shows "check your inbox" state; profile stores pending status |
| Educate account blocks IAM/Cognito | use a personal Free-plan account |
| Free-tier 12-month services (S3, API Gateway) expire | usage is fractions of a cent; budgets alert at $0.01; `make destroy` after demo |
| Secrets leaking into git | SSM only, `.gitignore`, `ruff`/`gitleaks` check in CI |

## 15. Possible later improvements (all still free)

- Add another keyless SA source (e.g. remote jobs open to South Africa) behind the same SQS queue.
- Amazon Comprehend experiment for skill extraction (free tier: 50k units/month for 12 months).
- Weekly "market report" email to all alert subscribers.
- Province choropleth map of South Africa on the dashboard.
