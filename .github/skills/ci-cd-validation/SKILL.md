---
name: ci-cd-validation
description: "Pre-commit checks, n8n JSON schema validation, lint rules, environment variable enforcement, and Docker auto-deploy/rollback with health endpoints."
user-invocable: true
---

# 🚀 Skill: ci-cd-validation

> Pre-commit checks, n8n JSON schema validation, lint rules, environment variable enforcement, and Docker auto-deploy/rollback with health endpoints.

---

## 🗂️ Repo Structure Assumptions

```
repo/
├── .github/
│   ├── copilot-instructions.md       ← Main Copilot skill
│   ├── copilot-skills/               ← All domain skills (this file lives here)
│   └── workflows/
│       ├── ci.yml                    ← Main CI pipeline
│       └── deploy.yml                ← Docker deploy + rollback
├── backend/
│   └── src/
├── frontend/
│   └── src/
├── n8n/
│   └── workflows/
│       └── *.json                    ← n8n workflow exports
├── .pre-commit-config.yaml
├── docker-compose.yml
└── .env.example                      ← Required env vars, committed (no values)
```

---

## 🔍 n8n Workflow JSON Schema Validation

### What to validate in every `n8n/workflows/*.json`
```python
# scripts/validate_n8n_workflows.py
"""Pre-commit and CI check for n8n workflow JSON exports."""
import json, sys, pathlib

REQUIRED_WORKFLOW_FIELDS = {"name", "nodes", "connections", "active", "settings"}
REQUIRED_NODE_FIELDS     = {"name", "type", "typeVersion", "position", "parameters"}
BANNED_PATTERNS = [
    "hardcoded_secret",     # literal secret strings (checked separately)
]

# Nodes that must always appear in queue alert workflows
REQUIRED_NODE_TYPES = {
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.if",          # auth check
    "n8n-nodes-base.telegram",
}

# Nodes that must be NAMED correctly (not left as defaults)
DEFAULT_NAMES_BANNED = {"Webhook", "IF", "Switch", "Telegram", "Set", "Code"}


def validate_workflow(path: pathlib.Path) -> list[str]:
    errors = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]

    # Top-level fields
    for f in REQUIRED_WORKFLOW_FIELDS:
        if f not in data:
            errors.append(f"Missing required field: '{f}'")

    nodes = data.get("nodes", [])

    for node in nodes:
        # Required node fields
        for f in REQUIRED_NODE_FIELDS:
            if f not in node:
                errors.append(f"Node missing field '{f}': {node.get('name', '?')}")

        # Banned default names
        if node.get("name") in DEFAULT_NAMES_BANNED:
            errors.append(
                f"Node has default name '{node['name']}' — use descriptive names "
                f"like 'Receive Queue Metrics' or 'Validate Webhook Secret'"
            )

    # Check that alert workflows have required node types
    node_types = {n.get("type") for n in nodes}
    if "n8n-nodes-base.webhook" in node_types:   # only check webhook workflows
        for required in REQUIRED_NODE_TYPES:
            if required not in node_types:
                errors.append(f"Queue alert workflow missing required node type: {required}")

    # Check webhook path is not the default
    for node in nodes:
        if node.get("type") == "n8n-nodes-base.webhook":
            path_val = node.get("parameters", {}).get("path", "")
            if path_val in {"", "webhook", "data", "queue"}:
                errors.append(f"Webhook node has insecure/default path: '{path_val}'")

    return errors


if __name__ == "__main__":
    workflow_files = list(pathlib.Path("n8n/workflows").glob("*.json"))
    if not workflow_files:
        print("No workflow files found in n8n/workflows/")
        sys.exit(0)

    all_ok = True
    for f in workflow_files:
        errs = validate_workflow(f)
        if errs:
            print(f"\n❌ {f.name}:")
            for e in errs:
                print(f"   - {e}")
            all_ok = False
        else:
            print(f"✅ {f.name}")

    sys.exit(0 if all_ok else 1)
```

---

## 🔒 Required Environment Variables Check

### `.env.example` (commit this — no values)
```env
# n8n Integration
N8N_WEBHOOK_URL=
N8N_WEBHOOK_SECRET=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# n8n self-hosted
N8N_HOST=
N8N_PORT=5678
N8N_PROTOCOL=https
WEBHOOK_URL=
N8N_BASIC_AUTH_USER=
N8N_BASIC_AUTH_PASSWORD=

# Backend
CAMERA_SOURCE=           # webcam|rtsp|file
RTSP_URL=               # only if CAMERA_SOURCE=rtsp
YOLO_MODEL_SIZE=small   # nano|small|medium|large|xlarge
```

### CI Script – Check Required Vars Are Set
```bash
#!/usr/bin/env bash
set -e

REQUIRED_VARS=(
  "N8N_WEBHOOK_URL"
  "N8N_WEBHOOK_SECRET"
  "TELEGRAM_CHAT_ID"
  "TELEGRAM_BOT_TOKEN"
)

missing=0
for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var}" ]]; then
    echo "❌ Missing required env var: $var"
    missing=1
  else
    echo "✅ $var is set"
  fi
done

exit $missing
```

---

## ⚙️ GitHub Actions: CI Pipeline

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: pip install -r backend/requirements.txt pytest ruff

      - name: Lint Python (ruff — PEP8 + isort)
        run: ruff check backend/src/ tests/

      - name: Run tests
        run: pytest tests/ -v --tb=short

      - name: Validate n8n workflow JSON
        run: python scripts/validate_n8n_workflows.py

      - name: Check env var documentation
        run: |
          # Ensure .env.example lists all vars used in code
          python scripts/check_env_coverage.py

  lint-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache-dependency-path: frontend/package-lock.json

      - name: Install deps
        run: cd frontend && npm ci

      - name: TypeScript check
        run: cd frontend && npx tsc --noEmit

      - name: ESLint
        run: cd frontend && npx eslint src/ --max-warnings 0

      - name: Prettier check
        run: cd frontend && npx prettier --check src/

  pre-merge-env-check:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    env:
      N8N_WEBHOOK_URL:    ${{ secrets.N8N_WEBHOOK_URL }}
      N8N_WEBHOOK_SECRET: ${{ secrets.N8N_WEBHOOK_SECRET }}
      TELEGRAM_CHAT_ID:   ${{ secrets.TELEGRAM_CHAT_ID }}
      TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - name: Verify required secrets are configured
        run: bash scripts/check_env_vars.sh
```

---

## 🐳 Docker Auto-Deploy & Rollback

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: |
          docker build -t queue-backend:${{ github.sha }} ./backend
          docker tag queue-backend:${{ github.sha }} queue-backend:latest

      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host:     ${{ secrets.DEPLOY_HOST }}
```

### Health Endpoint (Python Backend)
```python
# backend/src/api/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Required by deploy pipeline for rollback decision."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "checks": {
            "video_capture": _check_video_capture(),
            "n8n_reachable": _check_n8n(),
        }
    }


def _check_video_capture() -> str:
    # Return "ok" or "degraded"
    ...


def _check_n8n() -> str:
    import requests, os
    try:
        r = requests.get(os.environ["N8N_HEALTH_URL"], timeout=2)
        return "ok" if r.ok else "degraded"
    except Exception:
        return "unreachable"
```

---

## 🪝 Pre-commit Config

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: check-json           # catches malformed n8n exports
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: check-added-large-files
        args: ["--maxkb=500"]   # block large model weight commits

  - repo: local
    hooks:
      - id: validate-n8n-workflows
        name: Validate n8n workflow JSON
        entry: python scripts/validate_n8n_workflows.py
        language: python
        pass_filenames: false

      - id: no-hardcoded-secrets
        name: Check for hardcoded secrets
        files: \.(py|json|yaml|yml|env)$
```

---

## ✅ CI/CD Validation Checklist

- [ ] `ruff` passes with zero errors on `backend/src/`
- [ ] `tsc --noEmit` passes on `frontend/src/`
- [ ] All `n8n/workflows/*.json` pass schema validation
- [ ] No default node names (`Webhook`, `IF`, `Set`, etc.) in workflow JSON
- [ ] All required secrets set in GitHub repo secrets
- [ ] `.env.example` updated when new env vars are added to code
- [ ] Docker health endpoint at `/health` returns `{"status": "ok"}`
- [ ] Deploy pipeline runs rollback on health check failure
- [ ] Pre-commit hooks installed locally (`pre-commit install`)

---

*Skill version: 1.0 — Queue Wait-Time Estimation System — March 2026*