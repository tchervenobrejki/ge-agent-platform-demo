#!/usr/bin/env bash
# Step 2: load the demo metrics into BigQuery.
#
# Creates the dataset and three small tables from data/bigquery/*.csv. The data
# is synthetic: campaign CAMP-2025-042 has a conversion drop on 2025-06-26, and
# the funnel shows why (57.1% drop-off at checkout).
#
# Safe to run more than once: each load replaces the table.

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

DATA="$REPO_ROOT/data/bigquery"

echo "Creating dataset $PROJECT_ID:$BQ_DATASET in $REGION ..."
bq --project_id="$PROJECT_ID" show "$BQ_DATASET" >/dev/null 2>&1 \
  || bq --project_id="$PROJECT_ID" mk --dataset --location="$REGION" \
       --description="Synthetic campaign metrics for the growth-risk agent" "$BQ_DATASET"

load() { # table schema
  echo "Loading $1 ..."
  bq --project_id="$PROJECT_ID" load --replace --source_format=CSV --skip_leading_rows=1 \
    "$BQ_DATASET.$1" "$DATA/$1.csv" "$2"
}
load campaign_daily  "campaign_id:STRING,date:DATE,impressions:INTEGER,clicks:INTEGER,conversions:INTEGER,spend_eur:FLOAT"
load funnel_daily    "date:DATE,step:STRING,users:INTEGER,drop_off_pct:FLOAT"
load support_tickets "ticket_id:STRING,date:DATE,category:STRING,summary:STRING"

echo "Check: the incident day in the funnel"
bq --project_id="$PROJECT_ID" query --use_legacy_sql=false \
  "SELECT step, users, drop_off_pct FROM \`$PROJECT_ID.$BQ_DATASET.funnel_daily\`
   WHERE date = '2025-06-26' ORDER BY users DESC"
