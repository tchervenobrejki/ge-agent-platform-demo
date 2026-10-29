#!/usr/bin/env bash
# Delete what setup/01-04 created, and switch off RAG Engine billing.
#
# The simplest way to remove everything is to delete the whole project:
#   gcloud projects delete "$PROJECT_ID"
# Use this script instead if you want to keep the project.
#
# Run `terraform destroy` for the deployed agents FIRST (see README.md): their
# Terraform state lives in the state bucket this script deletes.

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

echo "This deletes, in $PROJECT_ID:"
echo "  Cloud Run service $MCP_SERVICE, RAG corpora $POLICY_CORPUS_NAME and $SUPPORT_CORPUS_NAME,"
echo "  BigQuery dataset $BQ_DATASET, service account $CALLER_SA, bucket gs://$STATE_BUCKET"
echo "and sets the RAG Engine tier to Unprovisioned, which deletes ALL RAG Engine"
echo "data in this project and region, not only these corpora."
read -r -p "Type the project ID to continue: " answer
[ "$answer" = "$PROJECT_ID" ] || { echo "Cancelled."; exit 1; }

gcloud run services delete "$MCP_SERVICE" --project="$PROJECT_ID" --region="$REGION" --quiet || true

uv run --quiet --with "google-cloud-aiplatform==1.165.1" python - <<EOF
import vertexai
from vertexai import rag

vertexai.init(project="$PROJECT_ID", location="$REGION")
for corpus in rag.list_corpora():
    if corpus.display_name in ("$POLICY_CORPUS_NAME", "$SUPPORT_CORPUS_NAME"):
        print("Deleting corpus", corpus.display_name)
        rag.delete_corpus(corpus.name)
# Basic, the default tier, is billed while provisioned, even with no corpora.
print("Setting the RAG Engine tier to Unprovisioned")
rag.update_rag_engine_config(
    rag.RagEngineConfig(
        name="projects/$PROJECT_ID/locations/$REGION/ragEngineConfig",
        rag_managed_db_config=rag.RagManagedDbConfig(tier=rag.Unprovisioned()),
    )
)
EOF

bq --project_id="$PROJECT_ID" rm -r -f -d "$BQ_DATASET" || true
gcloud iam service-accounts delete "$CALLER_SA" --project="$PROJECT_ID" --quiet || true
gcloud storage rm -r "gs://$STATE_BUCKET" --quiet || true

echo "Done. Cloud Build's source images remain in Artifact Registry"
echo "(repository cloud-run-source-deploy); delete it in the console if you like."
