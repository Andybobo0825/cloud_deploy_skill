# Rule Catalog

The bundled scanner is intentionally lightweight and deterministic. It scans Terraform source text only; it does not evaluate modules, variables, provider defaults, Terraform plans, state, or live AWS resources.

| Rule ID | Pillar | Severity | Flags |
| --- | --- | --- | --- |
| `SEC-S3-PUBLIC` | Security | High | Public S3 ACLs, disabled S3 public access block controls, or bucket policies granting S3 actions to `Principal = "*"`. |
| `SEC-SG-PUBLIC-INGRESS` | Security | High | Security group ingress open to `0.0.0.0/0` or `::/0` on all ports or sensitive ports such as SSH, RDP, database, Redis, or Elasticsearch. |
| `REL-RDS-BACKUP` | Reliability | Medium | RDS instances or clusters without `backup_retention_period >= 1`. |
| `REL-RDS-MULTIAZ` | Reliability | Medium | RDS instances without explicit `multi_az = true`. |
| `OPS-CW-LOGS` | Operational Excellence | Medium | No `aws_cloudwatch_log_group` resource in the scanned Terraform set. |
| `OPS-CW-ALARMS` | Operational Excellence | Medium | No `aws_cloudwatch_metric_alarm` resource in the scanned Terraform set. |
| `OPS-TAGS` | Operational Excellence | Low | AWS resources without a `tags = ...` assignment or equivalent Auto Scaling `tag` block. |
| `COST-EC2-OVERSIZED` | Cost Optimization | Medium | EC2 instances using large demo-unfriendly sizes such as `*.24xlarge` or metal classes. |
| `COST-BUDGET` | Cost Optimization | Medium | No `aws_budgets_budget` resource in the scanned Terraform set. |
| `PERF-SCALING` | Performance Efficiency | Low | Compute resources without Auto Scaling/app autoscaling resources. |
| `PERF-CACHE` | Performance Efficiency | Low | Compute resources without an obvious cache or managed read-optimization resource. |

## Limitations

- Does not parse full HCL semantics.
- Does not resolve variables, locals, modules, dynamic blocks, or generated JSON.
- Does not inspect IAM policy documents deeply.
- Does not prove runtime architecture quality.
- Use as an early review gate before formal AWS Well-Architected workload review.
