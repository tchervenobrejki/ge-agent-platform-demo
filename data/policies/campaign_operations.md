# Campaign Operations Policy (Synthetic Demo)

## Live campaign controls
- Pausing a **live campaign** requires **manager approval** before execution.
- Emergency pauses (P1 checkout failures) may be initiated by ops but must create a remediation ticket.

## Budget and discount limits
- Budget increases above **20%** require VP sign-off.
- Discounts above **20%** are **not permitted** without VP approval.
- Discounts above **50%** are **prohibited** under all circumstances.

## Conversion drop rollback
- If conversion rate drops more than **15%** day-over-day after a campaign change, run the checkout funnel investigation playbook.
- Recommended actions: pause affected ad segment, escalate checkout engineering, notify campaign owner.

## Evidence requirements
- All recommended actions must cite BigQuery metrics and support/policy sources.
- Never recommend budget or discount changes without compliance check.
