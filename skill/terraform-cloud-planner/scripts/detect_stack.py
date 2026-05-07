#!/usr/bin/env python3
"""Detect a repository's app stack and Terraform hints for terraform-cloud-planner."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()


def exists(name: str) -> bool:
    return (ROOT / name).exists()


def read(path: Path, limit: int = 200_000) -> str:
    try:
        return path.read_text(errors="ignore")[:limit]
    except Exception:
        return ""


def find_files(pattern: str, max_count: int = 200) -> list[str]:
    return [str(p.relative_to(ROOT)) for p in ROOT.rglob(pattern) if ".git" not in p.parts][:max_count]

files = {"root_files": [p.name for p in ROOT.iterdir() if p.is_file()] if ROOT.exists() else []}

languages: set[str] = set()
frameworks: set[str] = set()
package_managers: set[str] = set()
runtime_hints: dict[str, object] = {}
infra: dict[str, object] = {}

if exists("package.json"):
    languages.add("JavaScript/TypeScript")
    package_managers.add("npm/yarn/pnpm")
    pkg = read(ROOT / "package.json")
    for fw in ["next", "react", "vue", "express", "nestjs", "vite"]:
        if re.search(rf'"{fw}"\s*:', pkg, re.I):
            frameworks.add(fw)

requirements = find_files("requirements.txt")
pyproject = exists("pyproject.toml")
if requirements or pyproject or find_files("*.py", 50):
    languages.add("Python")
    req_text = "\n".join(read(ROOT / r) for r in requirements[:5]) + read(ROOT / "pyproject.toml")
    for fw in ["flask", "fastapi", "django", "streamlit", "gunicorn", "uvicorn"]:
        if re.search(rf"\b{fw}\b", req_text, re.I):
            frameworks.add(fw)
    package_managers.add("pip/venv")

if find_files("go.mod", 5):
    languages.add("Go")
if find_files("pom.xml", 5) or find_files("build.gradle*", 5):
    languages.add("Java/JVM")
if find_files("*.csproj", 5):
    languages.add(".NET")

if exists("Dockerfile"):
    runtime_hints["dockerfile"] = "Dockerfile"
    df = read(ROOT / "Dockerfile")
    ports = re.findall(r"(?im)^\s*EXPOSE\s+(\d+)", df)
    if ports:
        runtime_hints["exposed_ports"] = sorted(set(ports))
    if "gunicorn" in df.lower():
        frameworks.add("gunicorn")

compose = find_files("docker-compose*.yml") + find_files("compose*.yml")
if compose:
    runtime_hints["compose_files"] = compose

ci_files = [f for f in ["buildspec.yml", "buildspec.yaml", ".github/workflows"] if exists(f)]
if ci_files:
    runtime_hints["ci_cd_hints"] = ci_files

# Scan app source for common ports if Dockerfile did not expose one.
ports: set[str] = set(runtime_hints.get("exposed_ports", []))
for rel in find_files("*.py", 80) + find_files("*.js", 80) + find_files("*.ts", 80):
    text = read(ROOT / rel, 50_000)
    for m in re.finditer(r"port\s*[=:]\s*(\d{2,5})", text, re.I):
        ports.add(m.group(1))
    for m in re.finditer(r"--port\s+(\d{2,5})", text, re.I):
        ports.add(m.group(1))
if ports:
    runtime_hints["candidate_ports"] = sorted(ports)

tf_files = find_files("*.tf", 500)
if tf_files:
    infra["terraform_files"] = tf_files
    resources: list[str] = []
    providers: set[str] = set()
    for rel in tf_files:
        text = read(ROOT / rel)
        resources.extend(re.findall(r'resource\s+"([^"]+)"\s+"([^"]+)"', text))
        providers.update(re.findall(r'source\s*=\s*"hashicorp/([^"]+)"', text))
    infra["providers"] = sorted(providers)
    infra["resource_types"] = sorted({r[0] for r in resources})
    infra["resource_count"] = len(resources)

result = {
    "repo_root": str(ROOT),
    "languages": sorted(languages),
    "frameworks": sorted(frameworks),
    "package_managers": sorted(package_managers),
    "runtime_hints": runtime_hints,
    "infra_hints": infra,
    "notable_files": files["root_files"],
}
print(json.dumps(result, indent=2, ensure_ascii=False))
