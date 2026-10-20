# Demo script (about 12 minutes)

Live app: https://dzc3ibsjqeo54.cloudfront.net
Repository: https://github.com/Sbusiso-tech/sa-job-market-cloud-analytics

Speak from this page. The times are a guide. If a click is slow, skip to the next sentence rather than waiting in silence.

## The day before

- Sign in on the live app and open **Admin**. If it is missing, sign out and in again (the admins group is read at sign-in).
- On **Alerts**, create one alert for a common skill such as **SQL**, leave the province empty, and click the AWS confirmation email. The page should say alerts are active.
- Open one past alert email and one green GitHub Actions run, so both are one click away.
- Do not start a pipeline run during the demo unless you mean to. A run takes 3–5 minutes and uses about 40 of the 250 free Adzuna calls for the day. The 05:00 run already proves the schedule.

## 1. Problem (1 minute)

Open the dashboard.

> Employers in South Africa post thousands of tech jobs, but the boards don't answer the question a student actually has: which skills are being asked for right now, what do they pay in rands, and where are the jobs? This app answers that from real postings, updated every morning.

Point at the five cards: jobs in the last 30 days, new this week, median salary, top skill, top province.

## 2. Live product (4 minutes)

**Skills and pay.** Scroll to "Most in-demand skills" and "Salary ranges by skill".

> Each bar is how many postings mention that skill, and the change against last week. Salaries are rand per year: the low end is the 25th percentile, the middle is the median, the high end is the 75th. A skill only gets a range when at least five jobs state a salary, so one odd posting can't set the number for a whole skill or province.

**Provinces.** Scroll to "Jobs by province".

> Gauteng and the Western Cape dominate. Every row has a count, a median and the skills that lead there. "Unknown" means the posting only said "South Africa" and named no city. "Remote" means the posting itself says the role is remote.

**A job.** Open **Jobs**, choose **Python** in the skill filter, and open the first result.

> The list is the real postings, newest first. Filtering keeps reading until the page is full, so a rarer skill still returns jobs. The detail shows the salary in rands, the province, and the skills we extracted from the text.

**Save and alerts.** Sign in. On the job, click **Save job**, then open **Saved**. Then open **Alerts** and show the SQL alert.

> Saving a job is per person. The user id comes from the sign-in token, not from the page, so one person cannot read another's saved jobs. An alert is "email me when a new job mentions these skills". AWS sends one confirmation email; after that, each morning's run sends one digest, not one email per job.

If you have the digest email, open it here. If not, say it arrives after the next 05:00 run and move on.

## 3. Architecture (2 minutes)

Switch to the repository README and the diagram.

> The browser only talks to CloudFront. Pages come from a private S3 bucket. `/api` goes to API Gateway, which checks the Cognito token. Public numbers are cached at the edge; personal and admin routes are not.
>
> Every morning at 05:00, EventBridge starts a Step Functions workflow. Ingest calls Adzuna, at most 40 calls, and puts one message per job on a queue. A Lambda processes each job: clean the text, find skills, turn the salary into rand per year, map the city to a province. When the queue is drained, another Lambda writes the dashboard statistics into DynamoDB. New jobs go out through the table's stream to an email matcher.

Then the deliverables table in the README, one row each: API Gateway, Lambda, DynamoDB, Cognito, infrastructure as code, S3 and CloudFront, the queue and the workflow, SNS, and IAM.

## 4. Infrastructure as code and CI (2 minutes)

Open `infra/template.yaml` and `.github/workflows/ci.yml`. Then open the Actions tab and the latest green run on `main`.

> The whole account layout is this one template. `make deploy` creates it and `make destroy` removes it. Nothing is clicked together in the console.
>
> Every push runs lint, the test suites and a build. A push to `main` then deploys. GitHub signs in to AWS with a short-lived token. There is no access key stored in GitHub, and only this repository's `main` branch can assume the deploy role.

In the run log, the line that matters is "Assuming role with OIDC" followed by a successful deploy.

## 5. Cost (1 minute)

Open [docs/cost.md](cost.md) and the October bill image.

> The October bill is zero US dollars. Every service sits inside the AWS free allowances. DynamoDB is the one to watch: 20 of the 25 free capacity units are reserved on purpose, whether or not they are used. Two budgets email me if anything starts to cost money. The design bans the services that bill by the hour, such as a NAT gateway or a database server.

## 6. Close (1 minute)

> Three things I'd want you to remember. The statistics are computed once a day and stored, so the dashboard is a single cheap read. The queue is there so a few thousand jobs can be written without exceeding the free database capacity. And the deploy has no long-lived keys: GitHub proves who it is on each run.
>
> What I would add next is a signed-in recording of an alert arriving, and a second data source behind the same queue.

## If something breaks

| What you see | What to say |
|---|---|
| Dashboard looks empty | It is cached for up to 15 minutes after a run. Refresh, or use the README screenshots. |
| Admin link is missing | Sign out and in again. The group is only read at sign-in. |
| Alert email does not arrive during the demo | Confirmation must be clicked first, and only jobs added after the alert count. Show the Alerts page and explain the 05:00 run. |
| A GitHub check is red | Open the log. The last real failure was the deploy role rejecting GitHub's sign-in token; that is fixed and described in the retrospective. |
| Asked for a salary that looks too low | Medians need at least five stated salaries. Monthly figures filed as annual are treated as monthly when they are below a full-time floor. |
