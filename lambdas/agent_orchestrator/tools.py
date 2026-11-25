import json
import math
import os
import boto3

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
lambda_client = boto3.client("lambda")

BUCKET_NAME = os.environ["BUCKET_NAME"]
INDEX_KEY = os.environ.get("INDEX_KEY", "index/vectors.json")
EMBED_MODEL_ID = os.environ.get("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
BACKGROUND_WORKER_FN = os.environ.get("BACKGROUND_WORKER_FUNCTION_NAME", "BackgroundWorkflowLambda")

_VECTOR_CACHE = None


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _load_vectors() -> list[dict]:
    global _VECTOR_CACHE
    if _VECTOR_CACHE is not None:
        return _VECTOR_CACHE
    obj = s3.get_object(Bucket=BUCKET_NAME, Key=INDEX_KEY)
    _VECTOR_CACHE = json.loads(obj["Body"].read().decode("utf-8"))
    return _VECTOR_CACHE


def retrieve_documents(search_query: str, top_k: int = 3) -> list[dict]:
    """Embed query with Bedrock and retrieve top-k matching chunks from S3 index."""
    embed_body = json.dumps({
        "inputText": search_query,
        "dimensions": 512,
        "normalize": True
    })
    resp = bedrock.invoke_model(
        modelId=EMBED_MODEL_ID,
        body=embed_body,
        contentType="application/json",
        accept="application/json"
    )
    query_vec = json.loads(resp["body"].read().decode("utf-8"))["embedding"]

    vectors = _load_vectors()
    scored = []
    for item in vectors:
        score = _cosine_similarity(query_vec, item["embedding"])
        scored.append({
            "source": item["source"],
            "chunk_index": item["chunk_index"],
            "score": round(score, 4),
            "text": item["text"]
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def execute_background_workflow(workflow_type: str, severity: str, summary: str) -> dict:
    """Asynchronously invoke the background worker Lambda function."""
    payload = {
        "workflow_type": workflow_type,
        "severity": severity,
        "summary": summary
    }
    response = lambda_client.invoke(
        FunctionName=BACKGROUND_WORKER_FN,
        InvocationType="Event",
        Payload=json.dumps(payload).encode("utf-8")
    )
    return {
        "status": "dispatched_async",
        "workflow_type": workflow_type,
        "http_status": response.get("StatusCode")
    }