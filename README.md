# Autonomous Serverless Agentic RAG System on AWS

An autonomous, event-driven, serverless **Agentic Retrieval-Augmented Generation (RAG)** system built and deployed on **AWS (`ap-south-1`)**. Unlike passive single-shot chatbots, this system plans multi-step document lookups across private knowledge bases, evaluates operational policies (such as SLA severity rules), and asynchronously triggers background workflows—all with **$0 idle infrastructure cost**.

---

## Architecture Overview

```text
                              [ User / API Client ]
                                        |
                                        v (POST /)
                           [ Amazon API Gateway ]
                                        |
                                        v (Sync Invoke)
                          [ AgentOrchestratorLambda ]
                                  |         |
      +---------------------------+         +----------------------------+
      | (Bedrock Converse Loop)                                          | (Async Event)
      v                                                                  v
[ Amazon Bedrock ] <---> [ s3://.../index/vectors.json ]    [ BackgroundWorkflowLambda ]
  - Nova Pro               (Pure Python Cosine Search)                   |
  - Titan Embed V2                                                       v
                                                            [ s3://.../workflow-audits/ ]

==========================================================================================
EVENT-DRIVEN DOCUMENT INGESTION PIPELINE:

[ S3 Bucket: raw-docs/ ] ---> (ObjectCreated) ---> [ IngestionWorkerLambda ]
                                                            |
                                                            v
                                                   [ Amazon Bedrock ]
                                                 (Titan Text Embeddings)
                                                            |
                                                            v
                                            [ s3://.../index/vectors.json ]
```

### Core AWS Stack & Components
| Component | Service / Model | Role |
| :--- | :--- | :--- |
| **Orchestration Compute** | AWS Lambda (`AgentOrchestratorLambda`, Python 3.13) | Runs a bounded ReAct / Tool-Use loop (`max_steps=6`) via Amazon Bedrock Converse API, executes in-memory cosine similarity search, sanitizes `<thinking>` tags, and dispatches async tasks. |
| **Ingestion Pipeline** | AWS Lambda (`IngestionWorkerLambda`, Python 3.13) | Triggered automatically by S3 `ObjectCreated` events under `raw-docs/`. Chunks text (`500` chars, `100` overlap), embeds via Titan V2, and updates `index/vectors.json`. |
| **Background Worker** | AWS Lambda (`BackgroundWorkflowLambda`, Python 3.13) | Invoked asynchronously (`InvocationType='Event'`) to persist structured JSON incident audit records under `workflow-audits/` without blocking the user response. |
| **Foundation Models** | Amazon Bedrock (`apac.amazon.nova-pro-v1:0`, `amazon.titan-embed-text-v2:0`) | Cross-region inference profile for multi-step reasoning/tool calling + 512-dimensional embeddings. |
| **Storage & Vector Index** | Amazon S3 | Hosts source documents (`raw-docs/`), flat JSON vector store (`index/vectors.json`), and compliance audit records (`workflow-audits/`). |
| **API Layer & Telemetry** | Amazon API Gateway (HTTP API) & CloudWatch | Public `POST` endpoint with structured JSON logging for step latency, tool execution, and memory metrics. |

---

## Project Structure

```text
autonomous-agentic-rag/
├── lambdas/
│   ├── agent_orchestrator/
│   │   ├── agent_loop.py       # Bedrock Converse multi-step tool-use loop & output sanitization
│   │   ├── handler.py          # API Gateway Lambda proxy entrypoint
│   │   └── tools.py            # Cosine similarity retrieval & async background Lambda invocation
│   ├── background_worker/
│   │   └── handler.py          # Asynchronous audit record generator writing to S3
│   └── ingestion_worker/
│       └── handler.py          # S3-triggered document chunking & Titan embedding indexer
├── local_test/
│   └── run_local_agent.py      # End-to-end local harness for ingestion & agent testing
├── sample_docs/
│   ├── incident_runbook.md     # Sample operational remediation runbook
│   ├── sla_policy.md           # Sample incident severity & escalation policy
│   └── cache_runbook.md        # Sample Redis cache diagnostics runbook
├── docs/                       # Architecture reference & interview guide
├── requirements.txt
└── README.md
```

---

## Key Engineering Highlights

* **Zero-Bloat Cold-Start Optimization:** Built strictly with Python 3.13 standard libraries (`math`, `json`, `re`, `urllib`) and AWS's native `boto3` SDK—keeping zipped packages under **2 KB**, Lambda init durations around **380–500 ms**, and peak memory under **97 MB** (running on the 128 MB tier).
* **Cost-Optimized Serverless Vector Search:** Eliminates fixed managed vector database cluster costs ($0 idle cost) by storing dense embeddings in S3 (`index/vectors.json`) and performing sub-second in-memory cosine similarity inside Lambda.
* **Non-Blocking Async Decoupling:** Separates user-facing response generation from downstream administrative workflows using `InvocationType='Event'`, reducing API latency and isolating audit failures from the user path.
* **Agent Guardrails & Structured Observability:** Enforces bounded iteration limits (`max_steps=6`), strips internal model reasoning tags via regex, and emits structured JSON telemetry to CloudWatch Logs.

---

## Quick Start & Testing

### 1. Query the Live API Endpoint
Send a `POST` request with a `query` field to trigger multi-step document retrieval and autonomous workflow execution:

```powershell
$API_URL = "https://<your-api-id>.execute-api.ap-south-1.amazonaws.com"
$body = '{"query": "We are seeing HTTP 503 errors and remaining connection slots are reserved in CloudWatch for over 12 minutes. Check our runbook and SLA policy, and trigger the appropriate background workflow."}'

Invoke-RestMethod -Method Post -Uri $API_URL -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 5
```

### 2. Trigger Automatic Document Indexing via S3
Uploading any `.md` or `.txt` file to `raw-docs/` automatically invokes `IngestionWorkerLambda` and updates the vector index:

```powershell
aws s3 cp sample_docs/cache_runbook.md "s3://<your-bucket-name>/raw-docs/cache_runbook.md" --region ap-south-1
```

### 3. Verify Generated Audit Logs & CloudWatch Telemetry
```powershell
# List background workflow audit records in S3
aws s3 ls "s3://<your-bucket-name>/workflow-audits/" --recursive --region ap-south-1

# Tail structured JSON logs in CloudWatch
aws logs tail /aws/lambda/AgentOrchestratorLambda --since 15m --region ap-south-1 --format short
```

---

## Documentation
For a complete layman's walkthrough, architectural flow diagrams, deployment commands, and engineering trade-off notes, refer to the guide in the `docs/` folder (or the PDF guide in the repository root).