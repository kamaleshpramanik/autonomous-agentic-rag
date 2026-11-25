import datetime
import json
import os
import time
import uuid
import boto3

s3 = boto3.client("s3")
BUCKET_NAME = os.environ["BUCKET_NAME"]


def lambda_handler(event, context):
    start_time = time.time()
    workflow_type = event.get("workflow_type", "general_workflow")
    severity = event.get("severity", "P2")
    summary = event.get("summary", "")

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    record_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    audit_key = f"workflow-audits/{workflow_type}/{record_id}.json"

    audit_payload = {
        "record_id": record_id,
        "timestamp_utc": timestamp,
        "workflow_type": workflow_type,
        "severity": severity,
        "summary": summary,
        "status": "completed"
    }

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=audit_key,
        Body=json.dumps(audit_payload, indent=2).encode("utf-8"),
        ContentType="application/json"
    )

    elapsed_ms = round((time.time() - start_time) * 1000)
    print(json.dumps({
        "event": "background_workflow_completed",
        "record_id": record_id,
        "audit_key": audit_key,
        "duration_ms": elapsed_ms
    }))

    return {"statusCode": 200, "audit_key": audit_key}