#!/usr/bin/env bash
# Step 4: deploy the remediation MCP server to Cloud Run.
#
# The server (mcp-server/server.py) exposes one tool,
# create_remediation_action_mcp: the only write action in the whole pipeline.
# It is private: only the caller service account may invoke it, and the agent
# asks a human to approve every call before it is made.
#
# `gcloud run deploy --source` builds the container with Cloud Build from
# mcp-server/Dockerfile. Safe to run more than once: it deploys a new revision.

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

echo "Deploying $MCP_SERVICE (builds the image first, a few minutes) ..."
gcloud run deploy "$MCP_SERVICE" \
  --source="$REPO_ROOT/mcp-server" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --no-allow-unauthenticated \
  --port=8080 \
  --quiet

echo "Allowing $CALLER_SA to invoke it ..."
gcloud run services add-iam-policy-binding "$MCP_SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" \
  --member="serviceAccount:$CALLER_SA" --role="roles/run.invoker" >/dev/null

echo "Done. MCP endpoint: https://${MCP_SERVICE}-${PROJECT_NUMBER}.${REGION}.run.app/mcp"
