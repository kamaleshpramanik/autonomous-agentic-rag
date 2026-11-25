import json
import os
import time
import urllib.parse
import boto3

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")

BUCKET_NAME = os.environ["BUCKET_NAME"]
INDEX_KEY = os.environ.get("INDEX_KEY", "index/vectors.json")
EMBED_MODEL_ID = os.environ.get("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Split text into overlapping character chunks."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start += chunk_size - overlap
    return chunks


def get_embedding(text: str) -> list[float]:
    """Generate embedding vector using Amazon Bedrock Titan Embeddings V2."""
    body = json.dumps({
        "inputText": text,
        "dimensions": 512,
        "normalize": True
    })
    response = bedrock.invoke_model(
        modelId=EMBED_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json"
    )
    payload = json.loads(response["body"].read().decode("utf-8"))
    return payload["embedding"]


def load_existing_index(bucket: str, key: str) -> list[dict]:
    """Load existing vector records from S3 if present."""
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return []
    except Exception as exc:
        if "NoSuchKey" in str(exc):
            return []
        raise


def lambda_handler(event, context):
    start_time = time.time()
    records = event.get("Records", [])
    existing_index = load_existing_index(BUCKET_NAME, INDEX_KEY)

    indexed_count = 0
    for record in records:
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

        if not key.startswith("raw-docs/"):
            continue

        obj = s3.get_object(Bucket=bucket, Key=key)
        raw_text = obj["Body"].read().decode("utf-8", errors="replace")

        # Remove prior chunks for this source document before re-indexing
        existing_index = [item for item in existing_index if item.get("source") != key]

        chunks = chunk_text(raw_text)
        for idx, chunk in enumerate(chunks):
            vector = get_embedding(chunk)
            existing_index.append({
                "id": f"{key}#chunk-{idx}",
                "source": key,
                "chunk_index": idx,
                "text": chunk,
                "embedding": vector
            })
            indexed_count += 1

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=INDEX_KEY,
        Body=json.dumps(existing_index).encode("utf-8"),
        ContentType="application/json"
    )

    elapsed_ms = round((time.time() - start_time) * 1000)
    print(json.dumps({
        "event": "ingestion_complete",
        "chunks_indexed": indexed_count,
        "total_vectors_in_index": len(existing_index),
        "duration_ms": elapsed_ms
    }))

    return {
        "statusCode": 200,
        "body": json.dumps({
            "chunks_indexed": indexed_count,
            "total_vectors": len(existing_index),
            "duration_ms": elapsed_ms
        })
    }