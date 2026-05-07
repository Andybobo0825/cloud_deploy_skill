# AWS Terraform Intake Question Bank

Use only the questions needed for the current uncertainty. Keep user-facing questions short.

## Demo / Portfolio Defaults

- Region: prefer the user's nearest or existing project region; for Taiwan/HK demos, `ap-east-1` or `ap-northeast-1` are common choices.
- ECS/Fargate: `cpu=256`, `memory=512`, desired count `1`, public ALB if HTTP demo is needed.
- EC2 demo VM: `t3.micro`/`t4g.micro` where available, 8-20 GB gp3, SSH locked to user IP if needed.
- Logs: CloudWatch retention 7 or 14 days.
- Avoid by default: NAT Gateway, Multi-AZ RDS, WAF, ACM/Route53, VPC endpoints.

## Production Follow-ups

Ask production questions when the user says production/prd or implies real users/revenue:

1. Availability: single region, multi-AZ, active-passive DR, or multi-region?
2. Network: public ALB with private app subnets? NAT Gateway budget accepted?
3. Compute: min/max capacity, autoscaling metric, deployment strategy.
4. Data: database engine, size, Multi-AZ, backups, retention, encryption.
5. Security: secrets location, IAM boundaries, allowed ingress, audit logging.
6. Observability: dashboards, alarms, log retention, SLO/error budget.
7. Release: rollback, blue/green/canary, manual approvals.
8. Cost: monthly budget and resource deletion policy.

## AWS Service Mapping Hints

- Python Flask / FastAPI container: ECR + ECS Fargate + ALB + CloudWatch Logs.
- Static frontend: S3 + CloudFront + ACM + Route53 if domain exists.
- Background jobs: ECS scheduled task, Lambda, EventBridge, SQS depending duration/state.
- Relational data: RDS only if persistence is required; avoid for demo unless app needs DB.
- Secrets: SSM Parameter Store for simple demo; Secrets Manager for rotation/production.
- CI/CD: CodePipeline/CodeBuild if AWS-native pipeline is requested; GitHub Actions if repo-native pipeline is preferred.

## Implementation Profile Template

```markdown
# Terraform Intake

## Detected Stack
- Language/framework:
- Runtime/port:
- Container hints:
- Existing infra:

## Decisions
- Provider/region:
- Environment purpose:
- Runtime model:
- Scale:
- Sizing:
- Services:
- Availability:
- Security/networking:
- Cost guardrail:
- Naming/tags:

## Terraform Plan
- Files to create/change:
- Resources/modules:
- Variables/outputs:

## Assumptions
- ...

## Open Questions
- ...
```
