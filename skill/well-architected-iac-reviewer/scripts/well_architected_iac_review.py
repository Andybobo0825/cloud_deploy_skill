#!/usr/bin/env python3
"""Static AWS Well-Architected review for Terraform IaC.

Self-contained scanner for Codex skills. It scans Terraform text only and never
calls AWS APIs, downloads providers, reads Terraform state, or applies changes.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

RESOURCE_START = re.compile(r'(?m)^\s*resource\s+"(?P<type>[^"]+)"\s+"(?P<name>[^"]+)"\s*\{')
PUBLIC_CIDRS = ("0.0.0.0/0", "::/0")
OVERSIZED_INSTANCE_CLASSES = (
    "metal",
    "8xlarge",
    "9xlarge",
    "10xlarge",
    "12xlarge",
    "16xlarge",
    "18xlarge",
    "24xlarge",
    "32xlarge",
    "48xlarge",
    "56xlarge",
    "112xlarge",
)
RULE_IDS = (
    "SEC-S3-PUBLIC",
    "SEC-SG-PUBLIC-INGRESS",
    "REL-RDS-BACKUP",
    "REL-RDS-MULTIAZ",
    "OPS-CW-LOGS",
    "OPS-CW-ALARMS",
    "OPS-TAGS",
    "COST-EC2-OVERSIZED",
    "COST-BUDGET",
    "PERF-SCALING",
    "PERF-CACHE",
)
PILLAR_ORDER = (
    "Security",
    "Reliability",
    "Operational Excellence",
    "Cost Optimization",
    "Performance Efficiency",
)
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
FAIL_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class TerraformResource:
    type: str
    name: str
    body: str
    path: Path

    @property
    def address(self) -> str:
        return f"{self.type}.{self.name}"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    pillar: str
    severity: str
    title: str
    message: str
    path: Path | None = None
    resource: str | None = None
    recommendation: str = ""


@dataclass(frozen=True)
class ScanResult:
    scanned_files: tuple[Path, ...]
    findings: tuple[Finding, ...]
    passed_checks: tuple[str, ...] = field(default_factory=tuple)

    @property
    def finding_count_by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts


def strip_comments(text: str) -> str:
    cleaned_lines: list[str] = []
    in_block = False
    for line in text.splitlines():
        current = line
        if in_block:
            end = current.find("*/")
            if end == -1:
                continue
            current = current[end + 2 :]
            in_block = False
        while "/*" in current:
            start = current.find("/*")
            end = current.find("*/", start + 2)
            if end == -1:
                current = current[:start]
                in_block = True
                break
            current = current[:start] + current[end + 2 :]
        for marker in ("#", "//"):
            marker_at = current.find(marker)
            if marker_at != -1:
                current = current[:marker_at]
        cleaned_lines.append(current)
    return "\n".join(cleaned_lines)


def discover_tf_files(paths: list[Path]) -> tuple[Path, ...]:
    files: set[Path] = set()
    for path in paths:
        if path.is_file() and path.suffix == ".tf":
            files.add(path)
        elif path.is_dir():
            files.update(candidate for candidate in path.rglob("*.tf") if candidate.is_file() and ".terraform" not in candidate.parts)
    return tuple(sorted(files))


def parse_resources(path: Path) -> tuple[TerraformResource, ...]:
    text = strip_comments(path.read_text(encoding="utf-8"))
    resources: list[TerraformResource] = []
    for match in RESOURCE_START.finditer(text):
        body_start = match.end()
        body_end = find_matching_brace(text, body_start - 1)
        if body_end is None:
            continue
        resources.append(TerraformResource(match.group("type"), match.group("name"), text[body_start:body_end], path))
    return tuple(resources)


def find_matching_brace(text: str, opening_brace_at: int) -> int | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening_brace_at, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def scan_paths(paths: list[Path]) -> ScanResult:
    tf_files = discover_tf_files(paths)
    resources: list[TerraformResource] = []
    for tf_file in tf_files:
        resources.extend(parse_resources(tf_file))
    findings = evaluate(resources)
    failed_rule_ids = {finding.rule_id for finding in findings}
    passed = tuple(rule_id for rule_id in RULE_IDS if rule_id not in failed_rule_ids)
    return ScanResult(scanned_files=tf_files, findings=findings, passed_checks=passed)


def evaluate(resources: Iterable[TerraformResource]) -> tuple[Finding, ...]:
    resource_tuple = tuple(resources)
    findings: list[Finding] = []
    findings.extend(check_public_s3(resource_tuple))
    findings.extend(check_security_groups(resource_tuple))
    findings.extend(check_rds_reliability(resource_tuple))
    findings.extend(check_observability_and_tags(resource_tuple))
    findings.extend(check_cost(resource_tuple))
    findings.extend(check_performance(resource_tuple))
    return tuple(findings)


def check_public_s3(resources: tuple[TerraformResource, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for resource in resources:
        compact = compact_text(resource.body)
        if resource.type == "aws_s3_bucket" and re.search(r'\bacl\s*=\s*"?public-read', resource.body):
            findings.append(finding("SEC-S3-PUBLIC", "Security", "high", "Public S3 bucket ACL", "S3 bucket ACL allows public access.", resource, "Keep S3 buckets private and use CloudFront/OAC or signed URL patterns when public distribution is required."))
        if resource.type == "aws_s3_bucket_public_access_block":
            for field_name in ("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"):
                if re.search(rf'\b{field_name}\s*=\s*false\b', compact):
                    findings.append(finding("SEC-S3-PUBLIC", "Security", "high", "S3 public access block disabled", f"{field_name} is disabled, weakening S3 public access protection.", resource, "Set all S3 public access block controls to true unless a documented exception exists."))
                    break
        if resource.type == "aws_s3_bucket_policy" and '"*"' in resource.body and re.search(r's3:(GetObject|PutObject|\*)', resource.body, re.I):
            findings.append(finding("SEC-S3-PUBLIC", "Security", "high", "S3 bucket policy grants public principal", "Bucket policy grants S3 actions to Principal '*'.", resource, "Restrict principals to specific AWS identities and avoid anonymous S3 access."))
    return findings


def check_security_groups(resources: tuple[TerraformResource, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for resource in resources:
        if resource.type not in {"aws_security_group", "aws_security_group_rule", "aws_vpc_security_group_ingress_rule"}:
            continue
        body = resource.body
        if not any(cidr in body for cidr in PUBLIC_CIDRS):
            continue
        ingress_like = resource.type != "aws_security_group_rule" or re.search(r'\btype\s*=\s*"ingress"', body)
        if ingress_like and (allows_all_ports(body) or has_risky_public_port(body)):
            findings.append(finding("SEC-SG-PUBLIC-INGRESS", "Security", "high", "Permissive public ingress", "Security group ingress is open to the internet on all or sensitive ports.", resource, "Limit ingress CIDRs, prefer private connectivity, and document required public endpoints."))
    return findings


def check_rds_reliability(resources: tuple[TerraformResource, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for resource in resources:
        if resource.type not in {"aws_db_instance", "aws_rds_cluster"}:
            continue
        body = resource.body
        backup_match = re.search(r'\bbackup_retention_period\s*=\s*(\d+)', body)
        if not backup_match or int(backup_match.group(1)) < 1:
            findings.append(finding("REL-RDS-BACKUP", "Reliability", "medium", "RDS backup retention missing", "RDS resources should retain automated backups for recovery objectives.", resource, "Set backup_retention_period to at least 1 day for demos and align production values to RPO/RTO."))
        if resource.type == "aws_db_instance" and not re.search(r'\bmulti_az\s*=\s*true\b', compact_text(body)):
            findings.append(finding("REL-RDS-MULTIAZ", "Reliability", "medium", "RDS Multi-AZ signal missing", "RDS instance does not explicitly enable Multi-AZ resilience.", resource, "Use multi_az = true for production-like databases or document why a demo workload avoids the cost."))
    return findings


def check_observability_and_tags(resources: tuple[TerraformResource, ...]) -> list[Finding]:
    findings: list[Finding] = []
    if resources and not any(resource.type == "aws_cloudwatch_log_group" for resource in resources):
        findings.append(global_finding("OPS-CW-LOGS", "Operational Excellence", "medium", "CloudWatch log group missing", "No aws_cloudwatch_log_group resource was found.", "Add log groups with retention settings for workloads that emit logs."))
    if resources and not any(resource.type == "aws_cloudwatch_metric_alarm" for resource in resources):
        findings.append(global_finding("OPS-CW-ALARMS", "Operational Excellence", "medium", "CloudWatch alarm missing", "No aws_cloudwatch_metric_alarm resource was found.", "Add alarms for critical health, latency, error, and cost signals."))
    for resource in resources:
        if resource.type.startswith("aws_") and resource.type != "aws_iam_policy_document" and not has_tag_signal(resource):
            findings.append(finding("OPS-TAGS", "Operational Excellence", "low", "AWS resource missing tags", "AWS resource has no tags block for ownership, environment, or cost allocation.", resource, "Add common tags such as Project, Environment, Owner, and ManagedBy."))
    return findings


def has_tag_signal(resource: TerraformResource) -> bool:
    if resource.type in {"aws_s3_bucket_public_access_block"}:
        return True
    if re.search(r'\btags\s*=', resource.body):
        return True
    return resource.type == "aws_autoscaling_group" and re.search(r'(?m)^\s*tag\s*\{', resource.body) is not None

def check_cost(resources: tuple[TerraformResource, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for resource in resources:
        if resource.type == "aws_instance":
            instance_type = string_attr(resource.body, "instance_type")
            if instance_type and any(instance_type.endswith(f".{size}") or f".{size}." in instance_type for size in OVERSIZED_INSTANCE_CLASSES):
                findings.append(finding("COST-EC2-OVERSIZED", "Cost Optimization", "medium", "Oversized EC2 instance", f"EC2 instance type {instance_type} is large for a demo workload.", resource, "Use smaller burstable or Graviton instance classes unless load testing justifies capacity."))
    if resources and not any(resource.type == "aws_budgets_budget" for resource in resources):
        findings.append(global_finding("COST-BUDGET", "Cost Optimization", "medium", "Budget coverage missing", "No aws_budgets_budget resource was found.", "Add a monthly budget with notifications for demo environments."))
    return findings


def check_performance(resources: tuple[TerraformResource, ...]) -> list[Finding]:
    findings: list[Finding] = []
    has_compute = any(resource.type in {"aws_instance", "aws_launch_template", "aws_lb"} for resource in resources)
    has_scaling = any(resource.type in {"aws_autoscaling_group", "aws_appautoscaling_target", "aws_appautoscaling_policy"} for resource in resources)
    has_cache = any(resource.type.startswith("aws_elasticache") or resource.type == "aws_dynamodb_table" for resource in resources)
    if has_compute and not has_scaling:
        findings.append(global_finding("PERF-SCALING", "Performance Efficiency", "low", "Auto Scaling signal missing", "Compute resources exist without Auto Scaling configuration.", "Use Auto Scaling groups, app autoscaling targets, or document why fixed capacity is sufficient."))
    if has_compute and not has_cache:
        findings.append(global_finding("PERF-CACHE", "Performance Efficiency", "low", "Cache/read optimization signal missing", "Compute resources exist without an obvious cache or managed read-optimization service.", "Consider ElastiCache, DynamoDB, CDN, or query/cache design notes for read-heavy workloads."))
    return findings


def finding(rule_id: str, pillar: str, severity: str, title: str, message: str, resource: TerraformResource, recommendation: str) -> Finding:
    return Finding(rule_id, pillar, severity, title, message, resource.path, resource.address, recommendation)


def global_finding(rule_id: str, pillar: str, severity: str, title: str, message: str, recommendation: str) -> Finding:
    return Finding(rule_id, pillar, severity, title, message, recommendation=recommendation)


def compact_text(text: str) -> str:
    return re.sub(r'\s+', ' ', text).lower()


def string_attr(body: str, name: str) -> str | None:
    match = re.search(rf'\b{name}\s*=\s*"([^"]+)"', body)
    return match.group(1) if match else None


def allows_all_ports(body: str) -> bool:
    compact = compact_text(body)
    return bool(re.search(r'from_port\s*=\s*0\b', compact) and re.search(r'to_port\s*=\s*0\b', compact) and re.search(r'protocol\s*=\s*"?-?1"?', compact))


def has_risky_public_port(body: str) -> bool:
    risky_ports = {22, 3389, 3306, 5432, 6379, 9200, 9300}
    from_match = re.search(r'\bfrom_port\s*=\s*(\d+)', body)
    to_match = re.search(r'\bto_port\s*=\s*(\d+)', body)
    if not from_match or not to_match:
        return False
    start = int(from_match.group(1))
    end = int(to_match.group(1))
    return any(start <= port <= end for port in risky_ports)


def render_markdown(result: ScanResult) -> str:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "# AWS Well-Architected IaC Review",
        "",
        f"Generated: {generated_at}",
        "",
        "## Scope",
        "",
        f"- Terraform files scanned: {len(result.scanned_files)}",
        f"- Findings: {len(result.findings)}",
        "- Mode: static Terraform text analysis only; no AWS credentials, provider downloads, or Terraform apply.",
        "",
        "## Summary",
        "",
    ]
    if result.scanned_files:
        lines.append("Scanned files:")
        lines.extend(f"- `{path}`" for path in result.scanned_files)
    else:
        lines.append("No Terraform files were found in the requested paths.")
    lines.append("")
    severity_counts = Counter(finding.severity for finding in result.findings)
    lines.extend([
        "| Severity | Count |",
        "| --- | ---: |",
        f"| High | {severity_counts.get('high', 0)} |",
        f"| Medium | {severity_counts.get('medium', 0)} |",
        f"| Low | {severity_counts.get('low', 0)} |",
        "",
    ])
    if result.passed_checks:
        lines.extend(["## Checks Without Findings", ""])
        lines.extend(f"- `{rule_id}`" for rule_id in result.passed_checks)
        lines.append("")
    lines.extend(["## Findings", ""])
    if not result.findings:
        lines.extend(["No findings detected by the configured rule set.", ""])
    else:
        by_pillar: dict[str, list[Finding]] = defaultdict(list)
        for item in result.findings:
            by_pillar[item.pillar].append(item)
        for pillar in PILLAR_ORDER:
            findings = by_pillar.get(pillar, [])
            if not findings:
                continue
            lines.extend([f"### {pillar}", ""])
            for item in sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 99), f.rule_id, str(f.path), f.resource or "")):
                lines.extend([
                    f"#### {item.title} (`{item.rule_id}`)",
                    "",
                    f"- Severity: **{item.severity.upper()}**",
                    f"- Location: {location(item)}",
                    f"- Evidence: {item.message}",
                    f"- Recommendation: {item.recommendation}",
                    "",
                ])
    lines.extend([
        "## Next Steps",
        "",
        "- Review high-severity findings before merging infrastructure changes.",
        "- Keep exceptions documented with workload context, owner, and expiry date.",
        "- Run this reviewer in pull requests alongside `terraform fmt` and unit tests.",
        "",
    ])
    return "\n".join(lines)


def location(item: Finding) -> str:
    if item.path and item.resource:
        return f"`{item.path}` resource `{item.resource}`"
    if item.path:
        return f"`{item.path}`"
    return "repository-wide"


def should_fail(counts: dict[str, int], fail_on: str) -> bool:
    if fail_on == "none":
        return False
    threshold = FAIL_ORDER[fail_on]
    return any(count and FAIL_ORDER[severity] >= threshold for severity, count in counts.items())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Static AWS Well-Architected review for Terraform IaC.")
    parser.add_argument("paths", nargs="+", type=Path, help="Terraform files or directories to scan.")
    parser.add_argument("-o", "--output", type=Path, default=Path("architecture-review.md"), help="Markdown report path.")
    parser.add_argument("--fail-on", choices=("none", "low", "medium", "high"), default="none", help="Exit non-zero when findings at or above this severity exist.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    missing = [str(path) for path in args.paths if not path.exists()]
    if missing:
        print(f"error: path(s) not found: {', '.join(missing)}", file=sys.stderr)
        return 2
    result = scan_paths(args.paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(result), encoding="utf-8")
    counts = result.finding_count_by_severity
    print(
        "Scanned "
        f"{len(result.scanned_files)} Terraform file(s); wrote {args.output}; "
        f"findings={len(result.findings)} "
        f"high={counts.get('high', 0)} medium={counts.get('medium', 0)} low={counts.get('low', 0)}"
    )
    return 1 if should_fail(counts, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
