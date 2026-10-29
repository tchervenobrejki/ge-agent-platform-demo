"""BigQuery read-only tools for growth metrics investigation.

Queries the `demo_growth` dataset that setup/02_bigquery.sh creates.

An earlier version returned embedded fallback rows and KPI defaults whenever
BigQuery failed: invented numbers, which the spec forbids (F17 in
docs/design-decisions.md). Errors are returned as errors.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

from google.cloud import bigquery

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
DATASET = os.environ.get("BQ_DATASET", "demo_growth")

def _get_client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


def _is_read_only_sql(sql: str) -> bool:
    normalized = re.sub(r"\s+", " ", sql.strip().upper())
    if not normalized.startswith("SELECT"):
        return False
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE", "MERGE"]
    return not any(re.search(rf"\b{word}\b", normalized) for word in forbidden)


def execute_metrics_query(sql: str) -> dict[str, Any]:
    """Execute a read-only SQL query against growth metrics tables.

    Available tables in dataset `demo_growth`:
      - campaign_daily(campaign_id, date, impressions, clicks, conversions, spend_eur)
      - funnel_daily(date, step, users, drop_off_pct)
      - support_tickets(ticket_id, date, category, summary)

    Only SELECT queries are allowed. Write operations are blocked.

    Args:
        sql: A SELECT query against the demo_growth dataset tables.

    Returns:
        dict with status ('success' or 'error'), rows (list of dicts), row_count,
        and error_message when status is error.

    Examples:
        SELECT * FROM `<your-project-id>.demo_growth.campaign_daily`
        WHERE campaign_id = 'CAMP-2025-042' ORDER BY date
    """
    if not _is_read_only_sql(sql):
        return {
            "status": "error",
            "rows": [],
            "row_count": 0,
            "error_message": "Only read-only SELECT queries are permitted.",
        }

    try:
        client = _get_client()
        job = client.query(sql)
        rows = [dict(row.items()) for row in job.result()]
        for row in rows:
            for key, value in row.items():
                if hasattr(value, "isoformat"):
                    row[key] = value.isoformat()
        return {"status": "success", "rows": rows, "row_count": len(rows)}
    except Exception as exc:
        # No fabricated fallback rows: the spec forbids invented findings, and
        # an error lets sql_refinement_loop fix the query and retry.
        return {
            "status": "error",
            "rows": [],
            "row_count": 0,
            "error_message": str(exc),
        }


def calculate_kpi(metric_name: str, campaign_id: str, date: str) -> dict[str, Any]:
    """Calculate a KPI for a campaign on a specific date.

    Supported metrics: conversion_rate, click_through_rate, cost_per_conversion,
    checkout_drop_off_rate.

    Args:
        metric_name: KPI name (conversion_rate, click_through_rate,
            cost_per_conversion, checkout_drop_off_rate).
        campaign_id: Campaign identifier, e.g. 'CAMP-2025-042'.
        date: Date in YYYY-MM-DD format.

    Returns:
        dict with status, metric_name, value, unit, prior_day_value, and delta_pct.
    """
    metric = metric_name.strip().lower()
    try:
        if metric == "conversion_rate":
            sql = f"""
                SELECT date, clicks, conversions,
                  SAFE_DIVIDE(conversions, clicks) * 100 AS conversion_rate
                FROM `{PROJECT_ID}.{DATASET}.campaign_daily`
                WHERE campaign_id = @campaign_id AND date IN (@date, DATE_SUB(@date, INTERVAL 1 DAY))
                ORDER BY date
            """
            rows = _run_param_query(sql, campaign_id, date)
            if len(rows) >= 2:
                curr = float(rows[-1]["conversion_rate"])
                prior = float(rows[-2]["conversion_rate"])
                return _kpi_ok(metric, curr, "%", prior)
            if len(rows) == 1:
                curr = float(rows[0]["conversion_rate"])
                return _kpi_ok(metric, curr, "%", None)

        if metric == "click_through_rate":
            sql = f"""
                SELECT date, impressions, clicks,
                  SAFE_DIVIDE(clicks, impressions) * 100 AS ctr
                FROM `{PROJECT_ID}.{DATASET}.campaign_daily`
                WHERE campaign_id = @campaign_id AND date = @date
            """
            rows = _run_param_query(sql, campaign_id, date)
            if rows:
                return _kpi_ok(metric, float(rows[0]["ctr"]), "%", None)

        if metric == "cost_per_conversion":
            sql = f"""
                SELECT date, spend_eur, conversions,
                  SAFE_DIVIDE(spend_eur, conversions) AS cpc
                FROM `{PROJECT_ID}.{DATASET}.campaign_daily`
                WHERE campaign_id = @campaign_id AND date = @date
            """
            rows = _run_param_query(sql, campaign_id, date)
            if rows:
                return _kpi_ok(metric, float(rows[0]["cpc"]), "EUR", None)

        if metric == "checkout_drop_off_rate":
            sql = f"""
                SELECT drop_off_pct FROM `{PROJECT_ID}.{DATASET}.funnel_daily`
                WHERE date = @date AND step = 'checkout'
            """
            rows = _run_param_query(sql, campaign_id, date)
            if rows:
                return _kpi_ok(metric, float(rows[0]["drop_off_pct"]), "%", None)

        return {
            "status": "error",
            "metric_name": metric_name,
            "error_message": f"Unsupported metric or missing data for {metric_name}.",
        }
    except Exception as exc:
        return {
            "status": "error",
            "metric_name": metric_name,
            "error_message": str(exc),
        }


def _run_param_query(sql: str, campaign_id: str, date: str) -> list[dict[str, Any]]:
    client = _get_client()
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("campaign_id", "STRING", campaign_id),
            bigquery.ScalarQueryParameter("date", "DATE", date),
        ]
    )
    job = client.query(sql, job_config=job_config)
    return [dict(row.items()) for row in job.result()]


def _kpi_ok(
    metric: str, value: float, unit: str, prior: Optional[float]
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "success",
        "metric_name": metric,
        "value": round(value, 2),
        "unit": unit,
    }
    if prior is not None:
        result["prior_day_value"] = round(prior, 2)
        if prior != 0:
            result["delta_pct"] = round(((value - prior) / prior) * 100, 2)
    return result
