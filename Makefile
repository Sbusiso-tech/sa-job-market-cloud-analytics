# SA Job Market Cloud Analytics Platform
# Usage: make help. AWS commands use AWS_PROFILE (default sa-jobmarket) and region eu-west-1.

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c

AWS_PROFILE ?= sa-jobmarket
AWS_REGION ?= eu-west-1
STACK ?= sa-jobmarket
SCHEDULE_ENABLED ?= true
CREATE_BUDGET ?= true
SAMPLE ?= 0
GITHUB_OWNER ?= Sbusiso-tech
GITHUB_REPO ?= sa-job-market-cloud-analytics
GITHUB_OWNER_ID ?= $(shell gh api users/$(GITHUB_OWNER) --jq .id)
GITHUB_REPO_ID ?= $(shell gh api repos/$(GITHUB_OWNER)/$(GITHUB_REPO) --jq .id)
BOOTSTRAP_STACK ?= github-oidc-$(STACK)

# AWS_PROFILE= (as in CI, which uses OIDC credentials) must remove the variable: an empty profile breaks the AWS CLI.
ifeq ($(AWS_PROFILE),)
unexport AWS_PROFILE
else
export AWS_PROFILE
endif
export AWS_REGION
export AWS_DEFAULT_REGION := $(AWS_REGION)
export SAM_CLI_TELEMETRY := 0

VENV := backend/.venv
PY := $(VENV)/bin/python
TEMPLATE := infra/template.yaml
SAM_CONFIG := --config-file "$(CURDIR)/infra/samconfig.toml"
WEB_DIST := frontend/dist

# $(call stack_output,OutputKey) -> shell command printing one stack output
stack_output = aws cloudformation describe-stacks --stack-name $(STACK) --region $(AWS_REGION) \
	--query "Stacks[0].Outputs[?OutputKey=='$(1)'].OutputValue" --output text

.PHONY: help venv test lint demo build deploy outputs run-pipeline seed-secrets bootstrap-oidc \
	frontend-install frontend-build frontend-deploy destroy clean

help:
	@echo "venv            create backend/.venv (python3.12) with dev dependencies"
	@echo "test            run backend tests with coverage"
	@echo "lint            ruff + sam validate --lint"
	@echo "demo            offline demo on the bundled sample data"
	@echo "build           sam build"
	@echo "deploy          sam deploy (requires ADMIN_EMAIL=you@example.com; optional CFN_ROLE_ARN=...)"
	@echo "outputs         print stack outputs"
	@echo "run-pipeline    start a pipeline execution (SAMPLE=1 uses bundled sample data)"
	@echo "seed-secrets    store Adzuna keys in SSM (ADZUNA_APP_ID=... ADZUNA_APP_KEY=...)"
	@echo "bootstrap-oidc  one-time: GitHub OIDC provider and deploy roles for GitHub Actions"
	@echo "frontend-*      install / build / deploy the web app"
	@echo "destroy         empty both buckets and delete the stack"

venv:
	python3.12 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip
	$(VENV)/bin/pip install --quiet -r backend/requirements-dev.txt

test:
	(cd backend && .venv/bin/pytest --cov --cov-report=term --cov-fail-under=85)

lint:
	(cd backend && .venv/bin/ruff check src tests scripts)
	sam validate --lint -t $(TEMPLATE) --region $(AWS_REGION)
	$(VENV)/bin/cfn-lint infra/bootstrap/github-oidc.yaml

demo:
	$(PY) backend/scripts/demo_offline.py

build:
	sam build -t $(TEMPLATE) $(SAM_CONFIG)

deploy: build
	@if [ -z "$(ADMIN_EMAIL)" ]; then echo "ADMIN_EMAIL is required: make deploy ADMIN_EMAIL=you@example.com"; exit 1; fi
	sam deploy $(SAM_CONFIG) --stack-name $(STACK) --region $(AWS_REGION) \
		$(if $(CFN_ROLE_ARN),--role-arn $(CFN_ROLE_ARN)) \
		--parameter-overrides AdminEmail=$(ADMIN_EMAIL) ScheduleEnabled=$(SCHEDULE_ENABLED) CreateBudget=$(CREATE_BUDGET)
	dist_id="$$($(call stack_output,DistributionId))"
	aws cloudfront create-invalidation --distribution-id "$$dist_id" --paths "/api/public/*" \
		--query "Invalidation.Id" --output text

outputs:
	aws cloudformation describe-stacks --stack-name $(STACK) --region $(AWS_REGION) \
		--query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table

run-pipeline:
	arn="$$($(call stack_output,StateMachineArn))"
	if [ "$(SAMPLE)" = "1" ]; then input='{"use_sample": true}'; else input='{"use_sample": false}'; fi
	aws stepfunctions start-execution --region $(AWS_REGION) --state-machine-arn "$$arn" \
		--name "manual-$$(date -u +%Y%m%dT%H%M%SZ)" --input "$$input"

seed-secrets:
	@if [ -z "$(ADZUNA_APP_ID)" ] || [ -z "$(ADZUNA_APP_KEY)" ]; then \
		echo "usage: make seed-secrets ADZUNA_APP_ID=... ADZUNA_APP_KEY=..."; exit 1; fi
	@aws ssm put-parameter --region $(AWS_REGION) --name /sa-jobmarket/adzuna/app_id --type SecureString \
		--overwrite --value "$(ADZUNA_APP_ID)" > /dev/null
	@aws ssm put-parameter --region $(AWS_REGION) --name /sa-jobmarket/adzuna/app_key --type SecureString \
		--overwrite --value "$(ADZUNA_APP_KEY)" > /dev/null
	@echo "Adzuna keys stored in SSM Parameter Store under /sa-jobmarket/adzuna/"

bootstrap-oidc:
	aws cloudformation deploy --region $(AWS_REGION) --stack-name $(BOOTSTRAP_STACK) \
		--template-file infra/bootstrap/github-oidc.yaml --capabilities CAPABILITY_NAMED_IAM \
		--parameter-overrides GitHubOwner=$(GITHUB_OWNER) GitHubOwnerId=$(GITHUB_OWNER_ID) \
		GitHubRepo=$(GITHUB_REPO) GitHubRepoId=$(GITHUB_REPO_ID) AppStackName=$(STACK) \
		--tags project=sa-jobmarket
	aws cloudformation describe-stacks --region $(AWS_REGION) --stack-name $(BOOTSTRAP_STACK) \
		--query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table

frontend-install:
	npm --prefix frontend ci

frontend-build:
	npm --prefix frontend run build

frontend-deploy:
	bucket="$$($(call stack_output,WebBucketName))"
	dist_id="$$($(call stack_output,DistributionId))"
	pool="$$($(call stack_output,UserPoolId))"
	client="$$($(call stack_output,UserPoolClientId))"
	test -f $(WEB_DIST)/index.html || { echo "run make frontend-build first"; exit 1; }
	printf '{"apiBaseUrl":"/api","region":"%s","userPoolId":"%s","userPoolClientId":"%s","useMocks":false}\n' \
		"$(AWS_REGION)" "$$pool" "$$client" > $(WEB_DIST)/config.json
	aws s3 sync $(WEB_DIST) "s3://$$bucket" --delete --exclude index.html --exclude config.json \
		--exclude "assets/*" --cache-control "public, max-age=3600"
	if [ -d $(WEB_DIST)/assets ]; then aws s3 sync $(WEB_DIST)/assets "s3://$$bucket/assets" --delete \
		--cache-control "public, max-age=31536000, immutable"; fi
	aws s3 cp $(WEB_DIST)/index.html "s3://$$bucket/index.html" --cache-control "no-cache" \
		--content-type "text/html; charset=utf-8"
	aws s3 cp $(WEB_DIST)/config.json "s3://$$bucket/config.json" --cache-control "no-cache" \
		--content-type "application/json"
	aws cloudfront create-invalidation --distribution-id "$$dist_id" --paths "/index.html" "/config.json" \
		--query "Invalidation.Id" --output text

destroy:
	web="$$($(call stack_output,WebBucketName) 2>/dev/null || true)"
	data="$$($(call stack_output,DataBucketName) 2>/dev/null || true)"
	$(PY) backend/scripts/empty_bucket.py "$$web" "$$data"
	sam delete --stack-name $(STACK) --region $(AWS_REGION) --no-prompts

clean:
	rm -rf .aws-sam backend/.pytest_cache backend/.coverage backend/htmlcov backend/.ruff_cache
