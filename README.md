# SA Job Market Cloud Analytics Platform

[![CI](https://github.com/Sbusiso-tech/sa-job-market-cloud-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/Sbusiso-tech/sa-job-market-cloud-analytics/actions/workflows/ci.yml)

A serverless AWS application that tracks which tech skills South African employers are hiring for,
what they pay (in rands) and where (by province). Signed-in users can save jobs and get email
alerts for new jobs that match their skills.

Built as the capstone for the WeThinkCode_ Cloud Computing (AWS) programme, designed to run
entirely within the AWS free tier.

> Work in progress. See [PLAN.md](PLAN.md) for the full design and build phases.

## Tech stack

- **AWS:** API Gateway (HTTP API), Lambda (Python 3.12), DynamoDB, Cognito, S3, CloudFront,
  SQS, SNS, Step Functions, EventBridge Scheduler, CloudWatch, SSM Parameter Store
- **Infrastructure as Code:** AWS SAM / CloudFormation
- **Web app:** React, TypeScript, Vite
- **CI/CD:** GitHub Actions with OIDC deployment to AWS
- **Data source:** [Adzuna](https://developer.adzuna.com/) South Africa job search API
