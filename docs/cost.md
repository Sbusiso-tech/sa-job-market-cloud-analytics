# Cost

The platform is designed to cost **$0.00 a month**. Every service runs inside the AWS always-free allowances, or
(for API Gateway and S3) inside the 12-month free tier / Free-plan credits. This page shows the limits it was
designed against and the usage measured on the live deployment.

**Measured spend: $0.00.** Both AWS Budgets report $0.00 actual spend for October 2026 (as of 14 October).

## Guardrails

| Guardrail | Where | Purpose |
|---|---|---|
| Zero-spend budget | AWS account (created by hand) | Emails as soon as anything costs a cent |
| `sa-jobmarket-monthly-1usd` budget | `infra/template.yaml` (`CreateBudget` parameter) | Emails when actual spend passes 1 cent, or the month's forecast passes $1 |
| No hourly-billed services | Design rule ([PLAN.md](../PLAN.md) section 4) | No NAT Gateway, VPC Lambdas, RDS, EC2, Fargate, Athena, Glue, Secrets Manager, Route 53, WAF |
| DynamoDB provisioned 20 RCU / 20 WCU in total | `infra/template.yaml` | On-demand mode and auto scaling are never free; 20/20 stays under the 25/25 always-free capacity |
| SQS trigger `MaximumConcurrency: 2` | `infra/template.yaml` | Spreads writes so 20 WCU is enough |
| Adzuna ≤ 40 calls per run | `IngestFn` | Stays inside the free API key (250/day, 2,500/month) |
| 7-day log retention on all 8 log groups | `infra/template.yaml` | Logs never grow towards the 5 GB free storage |
| S3 lifecycle: `raw/` 30 days, `curated/` 90 days | `infra/template.yaml` | Data bucket stays small |
| DynamoDB TTL: jobs expire 60 days after last seen | `infra/template.yaml` | Table stays small; TTL deletes are free |
| API throttling: 10 requests/s, burst 20 | HTTP API stage | Abuse can't drive request counts up |
| CloudFront edge caching of public statistics | Cache policy | Most dashboard traffic never reaches API Gateway or Lambda |
| 6 CloudWatch alarms | `infra/template.yaml` | Under the 10 free alarms |
| `make destroy` | `Makefile` | Removes everything after the demo |

## Usage against free limits

Measured from 9 October 2026 (first deploy) to 14 October 2026: 9 pipeline runs (4 manual, 5 scheduled), all
succeeded. Sources: AWS Free Tier usage (`aws freetier get-free-tier-usage`), CloudWatch metrics and service APIs.
The monthly projection assumes one scheduled run a day.

| Service | Free allowance (per month) | Measured, 9–14 Oct | Projected month | Share of allowance |
|---|---|---|---|---|
| Lambda requests | 1,000,000 (always free) | 379 | ~1,500 | 0.2% |
| Lambda compute | 400,000 GB-seconds (always free) | 555 GB-s | ~1,900 GB-s | 0.5% |
| DynamoDB read capacity | 25 RCU (18,600 RCU-hours, always free) | 20 RCU provisioned | 14,880 RCU-hours | 80% |
| DynamoDB write capacity | 25 WCU (18,600 WCU-hours, always free) | 20 WCU provisioned | 14,880 WCU-hours | 80% |
| DynamoDB storage | 25 GB (always free) | 6.6 MB, 6,044 items | < 50 MB | < 0.2% |
| DynamoDB Streams | 2,500,000 reads (always free) | 1 | < 100 | ~0% |
| SQS requests | 1,000,000 (always free) | 47,916 | ~260,000 | 26% |
| Step Functions | 4,000 state transitions (always free) | 105 | ~360 | 9% |
| EventBridge Scheduler | 14,000,000 invocations (always free) | 5 | 30 | ~0% |
| SNS email deliveries | 1,000 (always free) | 1 | < 200 | < 20% |
| SNS publishes | 1,000,000 (always free) | 40 | < 1,000 | ~0% |
| CloudWatch alarms | 10 (always free) | 6 | 6 | 60% |
| CloudWatch Logs storage | 5 GB (always free) | 148 KB | < 1 MB | ~0% |
| KMS requests (AWS-managed keys) | 20,000 (always free) | 23 | < 200 | ~1% |
| CloudFront | 1 TB and 10,000,000 requests (always free) | 62 requests, 0.3 MB | small | ~0% |
| Cognito (Lite) | 10,000 monthly active users (always free) | 1 user | a handful | ~0% |
| SSM Parameter Store | Standard parameters (free) | 2 parameters | 2 | — |
| AWS Budgets | 2 budgets (free) | 2 | 2 | 100% |
| API Gateway (HTTP API) | 1,000,000 calls (12-month free tier / credits) | 32 | < 5,000 | < 0.5% |
| S3 storage | 5 GB (12-month free tier / credits) | 5.1 MB (76 objects) | < 50 MB | < 1% |

### Reading the numbers

- **DynamoDB at 80%** is fixed, not usage-driven: provisioned capacity is counted every hour whether it is used
  or not. 20 of the 25 free units are allocated to this table and its two indexes. A second DynamoDB table in the
  same account would need to fit in the remaining 5/5.
- **SQS at 26%** is mostly empty receives: the Lambda trigger long-polls the queue continuously (44,472 of the
  47,916 requests). Only 11,309 messages were actually sent, one per job per run.
- **Budgets at 100%** means the two free budgets are used. A third budget would cost about $0.02 a day.
- **API Gateway and CloudFront requests are low** because public statistics are cached at the edge for 15 minutes.
- The usage report also shows 15 AWS Glue Data Catalog requests (always free, 1,000,000 allowed). This project
  doesn't use Glue.

## Things that would cost money (and are avoided)

| Avoided | Why | Used instead |
|---|---|---|
| Cost Explorer API | $0.01 per request | Budgets and the Free Tier usage API (both free) |
| DynamoDB on-demand / auto scaling | Never free / creates paid alarms | Fixed provisioned capacity |
| NAT Gateway, Lambdas in a VPC | Hourly charge | Lambdas outside a VPC, IAM-scoped access |
| Secrets Manager | $0.40 per secret per month | SSM Parameter Store SecureString |
| Athena, Glue | Per query / per crawler | Precomputed statistics in DynamoDB |
| Route 53 domain | Hosted zone and domain fees | The CloudFront default domain |
| X-Ray, WAF | Per trace / per rule | CloudWatch alarms and API throttling |
| Customer-managed KMS keys | $1 per key per month | AWS-managed keys |

## Account plan

The deployment uses an AWS **Free plan** account. It can't be billed: usage outside the always-free allowances is
taken from $100 of credits, and the account pauses rather than charging a card. The plan runs until
28 February 2027. Before then, either run `make destroy` or upgrade deliberately and keep watching the budget emails.

Never enable AWS Organizations or IAM Identity Center on a Free-plan account: doing so upgrades it to a paid plan.
