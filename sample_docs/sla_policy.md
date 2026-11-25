# Service Level Agreement (SLA) & Escalation Policy

## Priority 1 (P1 - Critical)
- Trigger: Core API outage or database connection exhaustion exceeding 85% capacity for over 10 minutes.
- Response Target: Acknowledge within 15 minutes; open an audit/incident record in the compliance bucket.
- Background Action: Trigger the `create_incident_audit` background workflow with incident summary and severity `P1`.

## Priority 2 (P2 - Degraded)
- Trigger: Elevated latency (> 500ms) with no core service outage.
- Response Target: Acknowledge within 2 hours; log diagnostic summary for daily review.