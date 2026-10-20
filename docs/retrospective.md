# Retrospective

Written after the platform was deployed and running on real Adzuna data, with a zero US dollar October bill
and a GitHub Actions deploy from `main`.

## What was completed

The capstone pieces are live in one AWS SAM stack in eu-west-1: an HTTP API with a Cognito authorizer, eight
Python Lambdas, one DynamoDB table, a private web bucket behind CloudFront, and a daily pipeline
(EventBridge, Step Functions, SQS, SNS). Signed-in users can save jobs and subscribe to email alerts. A push
to `main` lints, tests, builds and deploys without an AWS key stored in GitHub.

The first real run stored 1,570 jobs. By 20 October 2026 the dashboard was reporting 10,232 postings over
30 days, a median salary of R510,000 and DevOps as the top skill. Backend tests: 303, at 99% coverage.
Web app tests: 47.

## What went well

- **Deciding the cost rules before writing code.** Banning hourly services (NAT gateway, a database server,
  on-demand DynamoDB) meant the design never had to be ripped out to stay free.
- **One API contract.** `docs/api-contract.md` is shared by the Lambdas and the React app, and a test fails
  if a response drifts from it.
- **Precomputed statistics.** The dashboard is a handful of DynamoDB reads. There is no query engine to pay for
  or to operate.
- **The queue.** Ingest and processing are separate, so a slow Adzuna call does not block writes, and a bad
  message lands in a dead-letter queue instead of stopping the run.
- **Tests that mock AWS.** Almost every bug below was reproduced with a unit test before the fix was deployed.

## Bugs worth telling in an interview

**The deploy failed on a comment.** CloudFront rejects a cache-policy description longer than 128 characters.
The first deploy rolled the whole stack back. The fix was a shorter comment, deleting the failed stack, and
deploying again. Lesson: read the service limit, not just the template error.

**Statistics were computed before the jobs existed.** The workflow waited until SQS reported an empty queue.
Those counts lag, so the aggregate step ran while messages were still in flight and the dashboard undercounted.
The ingest function now records how many jobs it queued, the processor counts how many it finished, and the
workflow waits until processed plus failed equals queued. DynamoDB then rejected the attribute name
`processed` because it is a reserved word; the update uses an alias. Lesson: don't trust an approximate metric
for a decision that has to be exact.

**Filtering by skill returned empty pages.** DynamoDB applies a filter after it has read a page. Searching for
C# read 20 recent jobs, none of them mentioned C#, and the API returned an empty page with a "next" cursor.
The API now keeps reading until it has a full page of matches, stops at 300 scanned items so it cannot burn
the free read capacity, and returns a cursor that resumes at the last job it actually returned. A test seeds
jobs where only every seventh row matches. Lesson: `Limit` and `FilterExpression` do not mean "give me N
matches".

**A fix looked like it had not deployed.** After the skill-filter change, C# still returned no jobs. The
response header said the page was served from CloudFront and was several minutes old. Public API responses
are cached for 15 minutes, which is right for a dashboard and wrong for checking a deploy. `make deploy` now
clears `/api/public/*`. Lesson: when a serverless change "didn't work", check the cache before the code.

**A province called Unknown, and a salary of R62,400.** Adzuna lists some jobs only as "South Africa". All
205 Unknown jobs were like that. The mapper now looks at the job title, then at a "Location:" line in the
description, and treats phrases like "fully remote" as remote. It ignores a loose mention such as "offices in
Johannesburg and Durban", which is not where the job is. Re-seen jobs get their province updated. Unknown
fell to 146 on that run. Separately, the Eastern Cape median was R62,400 because a single posting set it.
Medians are now shown only when at least five jobs state a salary. Lesson: a derived field is only as good
as the rule for missing and thin data.

**GitHub would not run Actions, then AWS would not let it sign in.** GitHub had flagged the account, so the
profile and repository were hidden and Actions returned "disabled for this user". Support cleared it. The
first real deploy then failed because the AWS role trusted `repo:owner/name:ref:refs/heads/main`, while
GitHub's token identifies the repository by numeric ids as well as the name. The role now trusts that
id-based subject, which is also safer: a new repository with the same name could not deploy. Lesson: when a
platform says "not authorized", compare the token's claims with the trust policy instead of widening the role.

## What is still open

- `make destroy` has not been run against the live stack. The budget and the alarms are in place; a full
  teardown is the last untested command.
- A signed-in recording (save a job, show an alert email, show the admin page) is not in the README yet.
  The public pages are.
- About a thousand postings still have no province, because the source text never names a city.

## What I would do differently

- Deploy a tiny stack on day one. The CloudFront comment limit and the cache behaviour only showed up in a
  real account.
- Put the queued and processed counters in the design, not in a fix. Approximate queue depth was the wrong
  signal to bet the workflow on.
- Confirm the GitHub account can run Actions before writing the workflow. The workflow was fine; the account
  was not.

## Suggested improvements, still inside the free tier

- A second job source behind the same queue, so one board cannot skew the skills.
- A weekly market email to people who already have an alert.
- A province map on the dashboard. The table is accurate; a map is easier to read in a demo.
