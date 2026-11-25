import importlib.util
import json
import os
import sys
from pathlib import Path
import boto3

ROOT_DIR = Path(__file__).resolve().parent.parent
BUCKET_NAME = os.environ.get("BUCKET_NAME", "kamalesh-agentic-rag-kb-992382391792-mumbai")
os.environ["BUCKET_NAME"] = BUCKET_NAME

# Load ingestion_worker/handler.py explicitly by file path
ing_spec = importlib.util.spec_from_file_location(
    "ingestion_handler_mod", ROOT_DIR / "lambdas" / "ingestion_worker" / "handler.py"
)
ing_mod = importlib.util.module_from_spec(ing_spec)
ing_spec.loader.exec_module(ing_mod)
ingestion_handler = ing_mod.lambda_handler

# Add agent_orchestrator to sys.path for agent_loop and tools
sys.path.insert(0, str(ROOT_DIR / "lambdas" / "agent_orchestrator"))
from agent_loop import run_agentic_rag


def upload_and_index_sample_docs():
    s3 = boto3.client("s3")
    sample_dir = ROOT_DIR / "sample_docs"
    s3_event_records = []

    for doc_path in sample_dir.glob("*.md"):
        s3_key = f"raw-docs/{doc_path.name}"
        s3.upload_file(str(doc_path), BUCKET_NAME, s3_key)
        s3_event_records.append({
            "s3": {
                "bucket": {"name": BUCKET_NAME},
                "object": {"key": s3_key}
            }
        })

    result = ingestion_handler({"Records": s3_event_records}, None)
    print("Ingestion Result:", json.dumps(result, indent=2))


if __name__ == "__main__":
    upload_and_index_sample_docs()

    prompt = (
        "We are seeing HTTP 503 errors and 'remaining connection slots are reserved' "
        "in CloudWatch for over 12 minutes. Check our runbook and SLA policy, and trigger "
        "the appropriate background workflow."
    )
    output = run_agentic_rag(prompt)
    print("\n--- FINAL AGENT RESPONSE ---")
    print(output["answer"])
    print("\n--- EXECUTION TRACE ---")
    print(json.dumps(output["trace"], indent=2))