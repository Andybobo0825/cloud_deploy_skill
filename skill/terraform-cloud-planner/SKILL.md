---
name: terraform-cloud-planner
description: Guided Terraform/IaC planning workflow for cloud infrastructure creation or modification. Use when Codex is asked to create, generate, scaffold, or change Terraform after first understanding the application's language/framework, deployment shape, environment purpose (demo/staging/production), cloud resource count, VM/container sizing, scale, AWS region, services, cost/HA/security constraints, and then producing a normalized Terraform plan before editing infra files.
---

# Terraform Cloud Planner

## Goal

Create Terraform only after a short architecture discovery and brainstorming intake. The skill prevents ad-hoc infra generation by turning app facts and user choices into a normalized Terraform implementation plan.

## Mandatory Workflow

1. **Detect the current stack before asking cloud questions.**
   - Run `scripts/detect_stack.py <repo-root>` from this skill.
   - Inspect existing infra files if present (`infra/`, `*.tf`, Dockerfile, compose files, CI files).
   - Summarize evidence: language, framework, runtime port, package manager, container/deployment hints, existing Terraform modules/resources.

2. **Run a brainstorming intake before Terraform edits.**
   - Ask concise questions in batches; do not edit Terraform until the required intake is answered or explicitly marked as assumed.
   - Prefer one compact first round covering the required fields below.
   - If the user says “demo”, choose small, low-cost defaults after confirming region and critical services.
   - If the user says “prd/production”, ask deeper HA, security, backup, observability, and scaling questions.

3. **Normalize decisions into an implementation profile.**
   - Write or update `infra/terraform-intake.md` with:
     - detected app stack
     - assumptions
     - selected cloud/provider/region
     - environment purpose
     - service inventory
     - sizing profile
     - scale/availability
     - security/networking
     - cost guardrails
     - Terraform files to create/change
     - open questions

4. **Only then create or edit Terraform.**
   - Keep existing architecture language/framework boundaries.
   - Prefer small, reviewable Terraform changes in existing `infra/` layout.
   - Do not create production-grade resources when the profile says demo unless requested.
   - Do not use credentials or apply infrastructure unless the user explicitly asks and authority exists.

5. **Verify.**
   - Run `terraform fmt -recursive` for changed Terraform.
   - Run `terraform validate` when provider/init context is available.
   - If validation cannot run, record the reason and run the next-best static check.

## Required Intake Fields

Collect or explicitly assume these before Terraform edits:

- Cloud provider and region, e.g. AWS `ap-east-1`, `ap-northeast-1`, `us-east-1`.
- Environment purpose: demo, portfolio, staging, production, or DR.
- Expected traffic/scale: users, requests per second, jobs, data size, growth window.
- Runtime model: VM, container, serverless, managed platform, or existing choice.
- Compute sizing:
  - VM: instance family/size, OS, disk size.
  - Container: CPU/memory, desired count, port, health check.
  - Serverless: memory, timeout, concurrency.
- Required services: network, load balancer, DNS/TLS, registry, database, cache, queue, secrets, logging, monitoring, CI/CD.
- Availability: single-AZ vs multi-AZ, autoscaling, rolling deployment, backup/restore.
- Security: public/private subnets, ingress sources, secrets handling, IAM boundary, encryption.
- Budget guardrail and cleanup policy.
- Naming/tagging convention.

Use `references/aws-question-bank.md` for deeper AWS-specific prompts and defaults.

## First-Round Question Template

After stack detection, ask something like:

```text
我偵測到：<language/framework/runtime/port/infra hints>。
在建立 Terraform 前，請先確認這 6 點：
1. 這是 demo/作品集、staging，還是 production？
2. AWS region 要用哪個？若沒偏好，我會建議 <region default>。
3. Runtime 要用 VM、ECS/Fargate container、Lambda，還是沿用目前架構？
4. 預估規模：低流量 demo、一般小型服務、或需要 autoscaling/HA？
5. 需要哪些服務：ALB、ECR、ECS、RDS、S3、CloudWatch、Secrets、DNS/TLS、CI/CD？
6. 成本上限/清除策略：是否要最低成本並方便 terraform destroy？
```

## Demo Defaults

When the user chooses demo/portfolio and does not specify otherwise:

- Prefer minimal managed resources and easy teardown.
- Use one VPC, two public subnets only if the selected AWS service requires ALB/Fargate style deployment.
- Prefer Fargate or small VM over complex Kubernetes.
- Desired count: `1`; no autoscaling unless requested.
- Logs: CloudWatch basic retention 7-14 days.
- ECR image scan on push for container projects.
- Avoid paid extras: NAT Gateway, WAF, RDS Multi-AZ, private endpoints, Route 53/TLS unless requested.

## Production Gate

If the user says production/prd, do not apply demo defaults silently. Ask/confirm:

- Multi-AZ design, private subnets, NAT/egress strategy.
- Secrets manager/parameter store and encryption requirements.
- Autoscaling thresholds and deployment rollback policy.
- Backups, retention, RPO/RTO.
- Monitoring/alerts and access controls.
- Cost envelope and compliance constraints.

## Output Contract Before Editing Terraform

Before the first Terraform edit, produce a short visible summary:

```markdown
Mode: terraform-cloud-planner
Detected stack: ...
Terraform profile: demo|staging|production, region=..., runtime=..., scale=...
Resources to create/change: ...
Assumptions: ...
Proceeding to edit: infra/<files>
```

Then implement directly unless the remaining question is destructive, credential-gated, or materially changes scope.
