"""Shared setup for the notebooks: `from nbsetup import *` in each one's first cell.

Finds the repository, reads your project from gcloud, and exports the values
as environment variables so `%%bash` cells can use them too ($PROJECT,
$REGION, $REPO, ...).
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import warnings

from IPython.display import Code, Markdown, display

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*(deprecated|EXPERIMENTAL).*")


def gcloud(*args: str) -> str:
    return subprocess.check_output(["gcloud", *args], text=True).strip()


REPO = pathlib.Path(__file__).resolve().parent.parent
PROJECT = os.environ.get("PROJECT_ID") or gcloud("config", "get-value", "project")
PROJECT_NUMBER = gcloud("projects", "describe", PROJECT, "--format=value(projectNumber)")
REGION = os.environ.get("REGION", "europe-west3")

COMPLIANCE_URL = f"https://compliance-agent-{PROJECT_NUMBER}.{REGION}.run.app"
MCP_URL = f"https://remediation-mcp-server-{PROJECT_NUMBER}.{REGION}.run.app"
MCP_CALLER = f"growth-risk-mcp-caller@{PROJECT}.iam.gserviceaccount.com"
MODEL_ARMOR_TEMPLATE = f"projects/{PROJECT}/locations/{REGION}/templates/growth-risk-guard"

os.environ.update(
    PROJECT=PROJECT,
    PROJECT_NUMBER=PROJECT_NUMBER,
    REGION=REGION,
    REPO=str(REPO),
    COMPLIANCE_URL=COMPLIANCE_URL,
    MCP_URL=MCP_URL,
    MCP_CALLER=MCP_CALLER,
    MODEL_ARMOR_TEMPLATE=MODEL_ARMOR_TEMPLATE,
    CLOUDSDK_CORE_PROJECT=PROJECT,
    GOOGLE_CLOUD_PROJECT=PROJECT,
)


def engine() -> str:
    """The deployed orchestrator's resource name, written by `agents-cli deploy`."""
    metadata = REPO / "growth-risk-agent/deployment_metadata.json"
    if not metadata.exists():
        raise RuntimeError("No deployment yet: run notebooks/04_deploy.ipynb first.")
    name = json.loads(metadata.read_text())["remote_agent_runtime_id"]
    os.environ["ENGINE"] = name
    return name


def console(path: str) -> None:
    """Show a link to a Cloud console page for this project."""
    url = f"https://console.cloud.google.com/{path}{'&' if '?' in path else '?'}project={PROJECT}"
    display(Markdown(f"➡️ [{url.split('?')[0].removeprefix('https://console.cloud.google.com/')}]({url})"))


def show(path: str, start: str, *, lines: int | None = None, lang: str = "python") -> None:
    """Display a top-level block of a repo file, starting at the line containing `start`."""
    text = (REPO / path).read_text().splitlines()
    i = next(n for n, line in enumerate(text) if start in line)
    j = i + 1
    while j < len(text) and lines is None:
        line = text[j]
        if line and not line[0].isspace() and line[0] not in ")]}" and j > i + 1:
            break
        j += 1
    if lines:
        j = i + lines
    display(Markdown(f"`{path}`, line {i + 1}"))
    display(Code("\n".join(text[i:j]).rstrip(), language=lang))


print(f"Project {PROJECT} ({PROJECT_NUMBER}), region {REGION}, repo {REPO}")
