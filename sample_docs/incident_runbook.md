# Incident Runbook: Database Connection Pool Exhaustion

## Symptoms
- API Gateway returns HTTP 503 or Lambda timeouts during peak traffic.
- CloudWatch logs show `FATAL: remaining connection slots are reserved for non-replication superuser connections`.

## Remediation Steps
1. Check active database connections and terminate idle-in-transaction sessions older than 5 minutes.
2. Temporarily scale down non-critical batch workers or enable connection queueing.
3. If active connections remain above 85% for more than 10 minutes, escalate to Tier-2 Platform Engineering per SLA-P1.