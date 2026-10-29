#!/usr/bin/env bash
# Step 1: prepare the project.
#
#   - enables the APIs the setup scripts need (Terraform enables the rest later)
#   - creates the bucket that holds Terraform state
#   - creates the service account the orchestrator uses to call the two
#     private Cloud Run services (the compliance agent and the MCP server)
#   - lets you impersonate that service account, so the agent also works
#     when you run it on your own machine
#   - lets Cloud Build deploy from source with the default compute service account
#
# Safe to run more than once.

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

echo "Enabling APIs (takes a minute the first time) ..."
# The agents' Terraform enables its own core APIs; these are the ones the setup
# scripts, Agent Identity and the Agent Registry entry need on top.
gcloud services enable --project="$PROJECT_ID" \
  agentidentity.googleapis.com \
  agentidentitycredentials.googleapis.com \
  agentregistry.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  bigquery.googleapis.com \
  cloudapiregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  run.googleapis.com \
  storage.googleapis.com

echo "Creating the Terraform state bucket gs://$STATE_BUCKET ..."
if ! gcloud storage buckets describe "gs://$STATE_BUCKET" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://$STATE_BUCKET" --project="$PROJECT_ID" \
    --location="$REGION" --uniform-bucket-level-access --public-access-prevention
  # Versioning lets you recover an earlier state file if one gets corrupted.
  gcloud storage buckets update "gs://$STATE_BUCKET" --versioning
fi

echo "Creating the caller service account $CALLER_SA ..."
if ! gcloud iam service-accounts describe "$CALLER_SA" --project="$PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$CALLER_SA_NAME" --project="$PROJECT_ID" \
    --display-name="Growth-risk agent: caller of private Cloud Run services"
fi
# It needs no project roles. The deploy steps grant it roles/run.invoker on
# each private service, and the orchestrator's Terraform lets the deployed
# agent impersonate it.

ME="$(gcloud config get-value account 2>/dev/null)"
echo "Letting $ME impersonate it (for running the agent locally) ..."
gcloud iam service-accounts add-iam-policy-binding "$CALLER_SA" --project="$PROJECT_ID" \
  --member="user:$ME" --role="roles/iam.serviceAccountTokenCreator" --condition=None >/dev/null

# `gcloud run deploy --source` builds with the default compute service account,
# which new projects no longer give any roles. Terraform grants the same role
# later; the MCP server deploy in step 4 needs it first.
echo "Granting Cloud Build permissions to the default compute service account ..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder" --condition=None >/dev/null

echo "Done."
