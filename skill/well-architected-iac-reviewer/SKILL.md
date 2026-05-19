---
name: well-architected-iac-reviewer
description: Static AWS Well-Architected review workflow for Terraform/IaC. Use after creating or modifying AWS Terraform, before deployment/apply, or when asked to scan IaC for security, reliability, operational excellence, cost, and performance risks. Produces an architecture-review.md report and can fail on selected finding severity without AWS credentials or Terraform execution.
---

# Well-Architected IaC Reviewer

## Goal

Review AWS Terraform before deployment by scanning local IaC text for common AWS Well-Architected risk signals and producing a Markdown architecture review report.

This skill is a **pre-deployment / PR review gate**, not a replacement for the AWS Well-Architected Tool or a full Terraform evaluator.

## Safety Boundaries

- Do not call AWS APIs.
- Do not require AWS credentials.
- Do not run `terraform apply`.
- Do not require provider downloads, state access, or live cloud access.
- Treat findings as architecture review prompts; document accepted risk instead of hiding it.

## Mandatory Workflow

1. **Select Terraform scope.**
   - Prefer the changed Terraform root such as `infra/`, `terraform/`, or the user-provided path.
   - If no scope is provided, inspect the repo for `*.tf` and choose the smallest relevant root.

2. **Run the bundled scanner.**
   - From this skill directory:

   ```bash
   python3 scripts/well_architected_iac_review.py <terraform-root> \
     --output architecture-review.md \
     --fail-on high
   ```

   - For advisory-only review, use `--fail-on none`.
   - For strict CI/PR review, use `--fail-on medium` or `--fail-on high`.

3. **Read and summarize the report.**
   - Report high and medium findings first.
   - Include rule IDs, affected resources, and recommended remediation.
   - State whether the review is blocking based on `--fail-on`.

4. **Fix or record exceptions.**
   - For generated Terraform, fix high-severity findings before handoff unless the user explicitly accepts the risk.
   - For demo/portfolio Terraform, prefer low-cost mitigations and clearly documented assumptions.
   - For production Terraform, do not silently downgrade security, backup, monitoring, or cost controls.

5. **Verify after fixes.**
   - Re-run the scanner after Terraform changes.
   - Also run `terraform fmt -recursive` and `terraform validate` when provider/init context is available.

## Implemented Review Areas

The scanner maps findings to AWS Well-Architected pillars:

- **Security**: public S3 ACL/policy/access-block weaknesses, public ingress on sensitive/all ports.
- **Reliability**: missing RDS backup retention or Multi-AZ signal.
- **Operational Excellence**: missing CloudWatch logs/alarms, missing AWS resource tags.
- **Cost Optimization**: oversized EC2 demo instances, missing AWS Budget.
- **Performance Efficiency**: compute without autoscaling or cache/read-optimization signal.

See `references/rule-catalog.md` for the exact rule IDs and limitations.

## Output Contract

After running the skill, respond with:

```markdown
Mode: well-architected-iac-reviewer
Scope: <paths scanned>
Report: <architecture-review.md path>
Findings: <count by severity>
Blocking status: pass|fail based on --fail-on
Top risks:
- <rule id> <severity> <resource/location> — <short recommendation>
Verification: <commands run and exit codes>
```
