#!/usr/bin/env bash
# Shared settings for the setup scripts. Sourced by each of them, not run directly.
#
# Override any value by exporting it before running a script, e.g.
#   export PROJECT_ID=my-project REGION=europe-west3

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Your Google Cloud project: PROJECT_ID if set, else the active gcloud project.
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "$PROJECT_ID" ]; then
  echo "Set a project first: gcloud config set project YOUR_PROJECT_ID" >&2
  exit 1
fi
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

# Everything regional runs here. The agents' Terraform uses the same default.
REGION="${REGION:-europe-west3}"

# Names of the resources the setup creates.
BQ_DATASET="${BQ_DATASET:-demo_growth}"
CALLER_SA_NAME="growth-risk-mcp-caller"
CALLER_SA="${CALLER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
MCP_SERVICE="remediation-mcp-server"
STATE_BUCKET="${PROJECT_ID}-terraform-state"
POLICY_CORPUS_NAME="growth-risk-policy-docs"
SUPPORT_CORPUS_NAME="growth-risk-support-docs"

export PROJECT_ID PROJECT_NUMBER REGION BQ_DATASET CALLER_SA MCP_SERVICE \
  STATE_BUCKET POLICY_CORPUS_NAME SUPPORT_CORPUS_NAME REPO_ROOT

echo "Project: $PROJECT_ID ($PROJECT_NUMBER), region: $REGION"
