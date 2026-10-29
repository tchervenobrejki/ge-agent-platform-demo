# /// script
# requires-python = ">=3.11"
# dependencies = ["google-cloud-aiplatform==1.165.1"]
# ///
"""Step 5: write your project's values into the config files.

    uv run setup/05_write_config.py

The repo ships with YOUR_* placeholders. This fills them in from what steps
1-4 created (it looks up the RAG corpora by name), so you don't copy IDs by
hand:

  growth-risk-agent/deployment/terraform/single-project/terraform.tfvars
  compliance-agent/deployment/terraform/single-project/terraform.tfvars
  platform/terraform/terraform.tfvars
  the three Terraform backend blocks (state bucket name)
  growth-risk-agent/.env and compliance-agent/.env  (for running locally)

Terraform loads terraform.tfvars automatically, which is what
`agents-cli infra single-project` relies on: it runs `terraform plan` with no
-var-file. Each one starts as a copy of the template next to it (vars/env.tfvars,
terraform.tfvars.example). The .tfvars and .env files it writes are gitignored.

Run it again after changing PROJECT_ID or REGION: it rewrites every value it
manages.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import vertexai
from vertexai import rag

REPO = Path(__file__).resolve().parent.parent
GRA_TF = REPO / "growth-risk-agent/deployment/terraform/single-project"
CA_TF = REPO / "compliance-agent/deployment/terraform/single-project"


def gcloud(*args: str) -> str:
    return subprocess.check_output(["gcloud", *args], text=True).strip()


PROJECT_ID = os.environ.get("PROJECT_ID") or gcloud("config", "get-value", "project")
PROJECT_NUMBER = gcloud("projects", "describe", PROJECT_ID, "--format=value(projectNumber)")
REGION = os.environ.get("REGION", "europe-west3")


def corpus(display_name: str) -> str:
    for c in rag.list_corpora():
        if c.display_name == display_name:
            return c.name
    raise SystemExit(f"Corpus {display_name} not found: run setup/03_rag_corpora.py first.")


vertexai.init(project=PROJECT_ID, location=REGION)
VALUES = {
    "project_id": PROJECT_ID,
    "region": REGION,
    "policy_rag_corpus": corpus("growth-risk-policy-docs"),
    "support_rag_corpus": corpus("growth-risk-support-docs"),
    "remediation_mcp_url": f"https://remediation-mcp-server-{PROJECT_NUMBER}.{REGION}.run.app/mcp",
    "mcp_caller_service_account": f"growth-risk-mcp-caller@{PROJECT_ID}.iam.gserviceaccount.com",
    "compliance_agent_url": f"https://compliance-agent-{PROJECT_NUMBER}.{REGION}.run.app/a2a/app",
}


def set_tfvars(path: Path, values: dict[str, str]) -> None:
    """Set `key = "value"` lines in a .tfvars file, keeping everything else."""
    text = path.read_text()
    for key, value in values.items():
        text, n = re.subn(rf'^({key}\s*=\s*)".*"', rf'\g<1>"{value}"', text, flags=re.M)
        if not n:
            text += f'{key} = "{value}"\n'
    path.write_text(text)
    print(f"wrote {path.relative_to(REPO)}")


def set_env(path: Path, template: Path, values: dict[str, str]) -> None:
    """Write KEY=value lines into a .env file, starting from .env.example."""
    text = (path if path.exists() else template).read_text()
    for key, value in values.items():
        text, n = re.subn(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)
        if not n:
            text += f"{key}={value}\n"
    path.write_text(text)
    print(f"wrote {path.relative_to(REPO)}")


def set_backend(path: Path) -> None:
    text = re.sub(r'bucket = "[^"]*"', f'bucket = "{PROJECT_ID}-terraform-state"', path.read_text())
    path.write_text(text)
    print(f"wrote {path.relative_to(REPO)}")


def tfvars_from(template: Path, target: Path) -> Path:
    if not target.exists():
        target.write_text(template.read_text())
    return target


set_tfvars(tfvars_from(GRA_TF / "vars/env.tfvars", GRA_TF / "terraform.tfvars"), VALUES)
set_tfvars(
    tfvars_from(CA_TF / "vars/env.tfvars", CA_TF / "terraform.tfvars"),
    {"project_id": PROJECT_ID, "region": REGION, "invoker_service_account": VALUES["mcp_caller_service_account"]},
)
set_tfvars(
    tfvars_from(REPO / "platform/terraform/terraform.tfvars.example", REPO / "platform/terraform/terraform.tfvars"),
    {"project_id": PROJECT_ID, "region": REGION},
)
for backend in [GRA_TF / "backend.tf", CA_TF / "backend.tf", REPO / "platform/terraform/providers.tf"]:
    set_backend(backend)

set_env(
    REPO / "growth-risk-agent/.env",
    REPO / "growth-risk-agent/.env.example",
    {
        "GOOGLE_CLOUD_PROJECT": PROJECT_ID,
        "GOOGLE_CLOUD_LOCATION": REGION,
        "BQ_DATASET": os.environ.get("BQ_DATASET", "demo_growth"),
        "POLICY_RAG_CORPUS": VALUES["policy_rag_corpus"],
        "SUPPORT_RAG_CORPUS": VALUES["support_rag_corpus"],
        "REMEDIATION_MCP_URL": VALUES["remediation_mcp_url"],
        "MCP_CALLER_SERVICE_ACCOUNT": VALUES["mcp_caller_service_account"],
        "COMPLIANCE_AGENT_URL": VALUES["compliance_agent_url"],
    },
)
set_env(
    REPO / "compliance-agent/.env",
    REPO / "compliance-agent/.env.example",
    {"GOOGLE_CLOUD_PROJECT": PROJECT_ID, "GOOGLE_CLOUD_LOCATION": REGION},
)
print("\nNext: deploy the compliance agent, then the orchestrator (see README.md).")
