# Checkout Conversion Drop Triage Runbook (Synthetic Demo)

## Symptoms
- Conversion rate drops while traffic/clicks increase after a campaign launch.
- Funnel analysis shows spike in drop-off at the **checkout** step.

## Known issues
- **Checkout timeout errors** on high-traffic days (spinner > 30 seconds).
- Payment gateway latency during peak campaign hours.

## Investigation steps
1. Compare conversion rate day-over-day for the campaign.
2. Inspect funnel_daily drop_off_pct at checkout step.
3. Search support tickets for checkout/payment complaints on the incident date.

## Escalation
- If checkout drop_off_pct > 50%, create **P1 remediation ticket**.
- Coordinate with campaign owner before pausing live segments.

## Sample support signals (2025-06-26)
- TKT-881: "Payment page timeout after 30s"
- TKT-882: "Cannot complete purchase, spinner forever"
- TKT-883: "Checkout broken since yesterday's promo campaign"
