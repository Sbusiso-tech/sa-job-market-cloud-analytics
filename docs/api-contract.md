# API contract

The single source of truth for request and response shapes shared by the backend
(`backend/src/handlers/api_*.py`) and the web app (`frontend/src/api/types.ts`).

- Base path: `/api`. The web app and API share one CloudFront origin, so there is no CORS in production.
- All bodies are JSON (`Content-Type: application/json`). Field names are `snake_case`.
- Dates are ISO 8601 strings in UTC (`2026-10-09T05:00:00Z`); `date_posted` may be a date only.
- Money is rand (ZAR) per year, rounded to whole rands, as numbers. `null` when unknown.
- Province values: `Gauteng`, `Western Cape`, `KwaZulu-Natal`, `Eastern Cape`, `Free State`,
  `Limpopo`, `Mpumalanga`, `North West`, `Northern Cape`, `Remote`, `Unknown`.
- Successful public responses send `Cache-Control: public, max-age=900`. Errors (any route), `/api/me/*`
  and `/api/admin/*` send `Cache-Control: no-store`.
- CloudFront caches public responses for up to 15 minutes. After a pipeline run the aggregate step
  invalidates `/api/public/*`, so public data can lag a manual run until that step finishes (a few minutes),
  and by at most 15 minutes if the invalidation fails.

## Nullable fields

Every field listed for a route is always present; "nullable" means its value may be `null`, never that
the key is missing.

- Before the first pipeline run: `last_updated` (every stats route), and in the overview `top_skill`,
  `top_province` and `median_salary_zar` are `null`. After a run, the overview's and each province row's
  `median_salary_zar` are `null` when fewer than 5 of the jobs counted have a salary.
- `Job`: `company` and `description_snippet` are always strings (`""` when unknown). `city`, `location`,
  `salary_min_zar`, `salary_max_zar`, `experience_years_min`, `experience_years_max`, `date_posted` and
  `url` may be `null`. `province` is `Unknown` rather than `null`; `seniority` and `employment_type` are
  `unspecified` rather than `null`.
- Saved job: `company` is `""` when unknown.
- `Alert.province` is always present and is `null` when the alert is for any province.
- `AlertsResponse.email` is `""` if the token carries no email.
- Admin `PipelineRun`: `stopped_at` is `null` while running; `fetched`, `new_jobs` and `failed` are `null`
  until the run records them.

## Errors

Every non-2xx response:

```json
{ "error": { "code": "not_found", "message": "Job not found" } }
```

| HTTP | code |
|---|---|
| 400 | `bad_request` |
| 401 | `unauthorized` (normally produced by API Gateway itself, whose body is `{"message":"Unauthorized"}`) |
| 403 | `forbidden` |
| 404 | `not_found` |
| 409 | `limit_reached` |
| 500 | `internal` |

## Authentication

- Cognito user pool, email as username. The web app signs in with SRP and sends the **ID token**:
  `Authorization: Bearer <id_token>` on `/api/me/*` and `/api/admin/*`.
- The API Gateway JWT authorizer checks issuer and audience (the app client id).
- Lambdas read `sub`, `email` and `cognito:groups` from the verified claims. Admin routes require
  the `admins` group, otherwise `403 forbidden`.

## Public routes (no auth)

### `GET /api/public/overview`

```json
{
  "last_updated": "2026-10-09T05:12:00Z",
  "window_days": 30,
  "total_jobs": 1240,
  "new_this_week": 210,
  "median_salary_zar": 540000,
  "top_skill": "SQL",
  "top_province": "Gauteng",
  "seniority": [{ "name": "senior", "count": 320 }],
  "employment_type": [{ "name": "full_time", "count": 900 }]
}
```

`seniority` names: `intern`, `junior`, `mid`, `senior`, `lead`, `unspecified`.
`employment_type` names: `full_time`, `part_time`, `contract`, `internship`, `temporary`, `unspecified`.
Before the first pipeline run every route returns the same shape with zeros, nulls and empty lists.

### `GET /api/public/skills`

Top 30 skills in the window.

```json
{
  "last_updated": "2026-10-09T05:12:00Z",
  "skills": [
    { "skill": "SQL", "category": "Programming Language", "count": 410, "share": 0.33, "change_vs_prev_week": 12 }
  ]
}
```

`share` = count / total_jobs (0–1, 3 decimals). `change_vs_prev_week` = this week's count minus
last week's count (integer, may be negative).

### `GET /api/public/skill-list`

Every skill the taxonomy knows, for pickers (alerts, job filters).

```json
{ "skills": [{ "name": "Python", "category": "Programming Language" }] }
```

`name` and `category` come from `backend/src/sajobs/skills_taxonomy.json`; treat `category` as a display
label, not an enum.

### `GET /api/public/salaries[?skill=Python]`

Skills with at least 5 jobs that have a salary. With `?skill=` the list has 0 or 1 entries.

```json
{
  "last_updated": "2026-10-09T05:12:00Z",
  "salaries": [{ "skill": "Python", "sample_size": 48, "p25": 420000, "median": 600000, "p75": 850000 }]
}
```

### `GET /api/public/provinces`

```json
{
  "last_updated": "2026-10-09T05:12:00Z",
  "provinces": [
    { "province": "Gauteng", "count": 610, "median_salary_zar": 580000,
      "top_skills": [{ "skill": "SQL", "count": 200 }] }
  ]
}
```

Sorted by `count` descending; `top_skills` has up to 5 entries.

### `GET /api/public/skill-pairs`

```json
{ "last_updated": "2026-10-09T05:12:00Z", "pairs": [{ "skills": ["Python", "SQL"], "count": 150 }] }
```

Top 20, skills inside a pair sorted alphabetically.

### `GET /api/public/trends`

Weekly snapshots, oldest first, up to 12 weeks.

```json
{
  "last_updated": "2026-10-09T05:12:00Z",
  "weeks": [{ "week": "2026-W41", "total_jobs": 300, "top_skills": [{ "skill": "SQL", "count": 90 }] }]
}
```

`last_updated` is `null` before the first run.

### `GET /api/public/jobs?province=&skill=&limit=&cursor=`

Newest first. All query parameters optional. Filtering by `skill` may return fewer than `limit` items
while `next_cursor` is still set.

- `limit`: integer 1–50, default 20. Anything else (non-integer, 0, 51) is `400 bad_request`.
- `province`: one of the province values (case-insensitive). An unknown province is `400 bad_request`.
- `cursor`: the opaque `next_cursor` from the previous page of the same `province` filter. A malformed
  cursor, or one from a different province listing, is `400 bad_request`.
- `skill`: case-insensitive, normalised to the taxonomy name (`python` matches `Python`). A skill the
  taxonomy does not know is not an error: `200` with `{ "items": [], "next_cursor": null }`.

```json
{ "items": [Job], "next_cursor": "eyJ..." }
```

`Job`:

```json
{
  "job_id": "3f2a…",
  "title": "Senior Data Engineer",
  "company": "Acme Bank",
  "location": "Sandton, Johannesburg",
  "city": "Sandton",
  "province": "Gauteng",
  "is_remote": false,
  "salary_min_zar": 600000,
  "salary_max_zar": 780000,
  "salary_is_predicted": false,
  "seniority": "senior",
  "employment_type": "full_time",
  "experience_years_min": 5,
  "experience_years_max": null,
  "skills": ["Python", "SQL", "AWS"],
  "date_posted": "2026-10-07T09:00:00Z",
  "url": "https://www.adzuna.co.za/details/…",
  "source": "adzuna",
  "description_snippet": "First 300 characters of the cleaned description…"
}
```

### `GET /api/public/jobs/{job_id}`

Returns one `Job`, or `404 not_found`.

## Signed-in user routes

### `GET /api/me/saved-jobs`

```json
{ "items": [{ "job_id": "3f2a…", "title": "…", "company": "…", "province": "Gauteng", "saved_at": "…" }] }
```

### `PUT /api/me/saved-jobs/{job_id}`

No body. `200` with the saved item (same shape as above). Idempotent. `404 not_found` if the job
does not exist.

### `DELETE /api/me/saved-jobs/{job_id}`

`204`, also when it was not saved.

### `GET /api/me/alerts`

```json
{
  "email": "user@example.com",
  "subscription_status": "pending_confirmation",
  "alerts": [
    { "alert_id": "a1b2c3", "skills": ["Python", "AWS"], "province": "Gauteng", "created_at": "…" },
    { "alert_id": "d4e5f6", "skills": ["SQL"], "province": null, "created_at": "…" }
  ]
}
```

`Alert.province` is always present: a province value, or `null` for "any province". Alerts are listed
oldest first.

`subscription_status`: `none` (no alerts yet), `pending_confirmation` (SNS sent a confirmation
email that has not been clicked), `confirmed`.

### `POST /api/me/alerts`

Body: `{ "skills": ["Python", "AWS"], "province": "Gauteng" }`. `skills` 1–5 known skill names
(case-insensitive, normalised to taxonomy names); `province` optional, one of the province values.
Max 5 alerts per user, otherwise `409 limit_reached`.

`201`:

```json
{ "alert": Alert, "subscription_status": "pending_confirmation" }
```

The first alert subscribes the user's email to the SNS `job-alerts` topic with a filter policy on
their `sub`; AWS then emails a confirmation link.

### `DELETE /api/me/alerts/{alert_id}`

`204`. When the last alert is deleted the SNS subscription is removed too.

### `DELETE /api/me`

`204`. Deletes every item for the user and their SNS subscription. The web app then deletes the
Cognito user itself (`deleteUser` with the user's own tokens) and signs out.

## Admin routes (`admins` group)

### `POST /api/admin/runs`

No body. Starts the pipeline state machine. `202`:

```json
{ "execution_id": "manual-20261009T081500Z", "started_at": "2026-10-09T08:15:00Z" }
```

Execution names have one-second resolution: a second start in the same second is `409 limit_reached`.

### `GET /api/admin/runs`

```json
{
  "dlq_depth": 0,
  "runs": [
    { "execution_id": "…", "status": "SUCCEEDED", "started_at": "…", "stopped_at": "…",
      "fetched": 380, "new_jobs": 95, "failed": 0 }
  ]
}
```

`status`: `RUNNING`, `SUCCEEDED`, `FAILED`, `TIMED_OUT`, `ABORTED`. Last 20 runs, newest first;
counts are `null` while unknown.
