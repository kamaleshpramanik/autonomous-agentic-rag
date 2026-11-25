import json
import time
from agent_loop import run_agentic_rag


def lambda_handler(event, context):
    start_time = time.time()
    try:
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        elif isinstance(event.get("body"), dict):
            body = event["body"]
        else:
            body = event

        query = (body.get("query") or "").strip()
        if not query:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing required 'query' field"})
            }

        result = run_agentic_rag(query)
        total_ms = round((time.time() - start_time) * 1000)

        print(json.dumps({
            "event": "request_completed",
            "steps_taken": result["steps_taken"],
            "total_latency_ms": total_ms
        }))

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "answer": result["answer"],
                "steps_taken": result["steps_taken"],
                "total_latency_ms": total_ms,
                "trace": result["trace"]
            })
        }

    except Exception as exc:
        print(json.dumps({
            "event": "request_error",
            "error": str(exc)
        }))
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(exc)})
        }