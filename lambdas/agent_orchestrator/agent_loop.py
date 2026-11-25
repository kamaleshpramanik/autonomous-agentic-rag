import json
import os
import re
import time
import boto3
from tools import execute_background_workflow, retrieve_documents

bedrock = boto3.client("bedrock-runtime")
CHAT_MODEL_ID = os.environ.get(
    "CHAT_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "retrieve_documents",
                "description": (
                    "Search private knowledge base documents (runbooks, SLA policies, SOPs). "
                    "Call this tool multiple times with different queries when you need information "
                    "from more than one document or policy."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "search_query": {
                                "type": "string",
                                "description": "Focused search query for the knowledge repository"
                            }
                        },
                        "required": ["search_query"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "execute_background_workflow",
                "description": (
                    "Trigger an asynchronous background workflow after retrieving relevant runbook "
                    "and SLA/policy details."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "workflow_type": {
                                "type": "string",
                                "description": "Workflow identifier, e.g., create_incident_audit"
                            },
                            "severity": {
                                "type": "string",
                                "description": "Incident severity level, e.g., P1 or P2"
                            },
                            "summary": {
                                "type": "string",
                                "description": "Concise findings and recommended action summary"
                            }
                        },
                        "required": ["workflow_type", "severity", "summary"]
                    }
                }
            }
        }
    ]
}

SYSTEM_PROMPT = (
    "You are an autonomous enterprise operations agent. "
    "Use retrieve_documents to gather facts from private knowledge repositories before answering. "
    "If a policy or SLA applies, perform a separate retrieval query for policy rules. "
    "When a user explicitly requests logging, auditing, or executing a workflow after gathering facts, "
    "call execute_background_workflow. Cite source document names in your final answer."
)


def run_agentic_rag(user_query: str, max_steps: int = 6) -> dict:
    messages = [{"role": "user", "content": [{"text": user_query}]}]
    execution_trace = []

    for step in range(1, max_steps + 1):
        step_start = time.time()
        response = bedrock.converse(
            modelId=CHAT_MODEL_ID,
            messages=messages,
            system=[{"text": SYSTEM_PROMPT}],
            toolConfig=TOOL_CONFIG,
            inferenceConfig={"temperature": 0.1, "maxTokens": 1024}
        )

        assistant_msg = response["output"]["message"]
        messages.append(assistant_msg)
        stop_reason = response.get("stopReason")

        if stop_reason == "end_turn":
            raw_text = "".join(
                block["text"] for block in assistant_msg.get("content", []) if "text" in block
            )
            answer_text = re.sub(r"<thinking>.*?</thinking>", "", raw_text, flags=re.DOTALL).strip()
            return {
                "answer": answer_text,
                "steps_taken": step,
                "trace": execution_trace
            }

        if stop_reason == "tool_use":
            tool_results = []
            for block in assistant_msg.get("content", []):
                if "toolUse" not in block:
                    continue
                tool_use = block["toolUse"]
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]
                tool_use_id = tool_use["toolUseId"]

                if tool_name == "retrieve_documents":
                    output_payload = retrieve_documents(tool_input["search_query"])
                elif tool_name == "execute_background_workflow":
                    output_payload = execute_background_workflow(
                        workflow_type=tool_input["workflow_type"],
                        severity=tool_input.get("severity", "P2"),
                        summary=tool_input["summary"]
                    )
                else:
                    output_payload = {"error": f"Unknown tool: {tool_name}"}

                step_ms = round((time.time() - step_start) * 1000)
                trace_entry = {
                    "step": step,
                    "tool": tool_name,
                    "input": tool_input,
                    "latency_ms": step_ms
                }
                execution_trace.append(trace_entry)
                print(json.dumps({"event": "agent_tool_execution", **trace_entry}))

                tool_results.append({
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"json": {"result": output_payload}}]
                    }
                })

            messages.append({"role": "user", "content": tool_results})

    return {
        "answer": "Stopped after reaching maximum agent reasoning steps.",
        "steps_taken": max_steps,
        "trace": execution_trace
    }