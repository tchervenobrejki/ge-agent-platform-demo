#!/usr/bin/env bash
# Generate -> enrich -> grade one dataset (docs/evaluation.md).
#
# `agents-cli eval run` can't be used directly: our SequentialAgent root makes
# ADK's /app-info return 400, so traces lack agent/tool definitions until
# enrich_traces.py adds them.
#
# Usage (from the project root, with the Compliance Agent reachable at
# COMPLIANCE_AGENT_URL -- locally: run it on :8001 with APP_URL set):
#   tests/eval/run_eval.sh tests/eval/datasets/task-cases.json tests/eval/eval_config.yaml
#   tests/eval/run_eval.sh tests/eval/guardrails/guardrail-cases.json tests/eval/eval_config_guardrails.yaml
set -euo pipefail

dataset="$1"
config="$2"
project="${GOOGLE_CLOUD_PROJECT:?Set GOOGLE_CLOUD_PROJECT to your project ID}"
trace="artifacts/traces/traces_$(basename "${dataset%.json}")_$(date +%Y%m%d_%H%M%S).json"

agents-cli eval generate --dataset "$dataset" -o "$trace" --concurrency 2
uv run python tests/eval/enrich_traces.py "$trace"
agents-cli eval grade --traces "$trace" --config "$config" --project "$project" --qps 5
