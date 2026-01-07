import base64
import json
import os
import uuid
from typing import Any, Dict

import awslambda
import boto3


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(event, dict) and "body" in event:
        body = event.get("body") or ""
        if event.get("isBase64Encoded") and body:
            body = base64.b64decode(body).decode("utf-8")
        return json.loads(body) if body else {}
    if isinstance(event, dict):
        return event
    return {}


def _write_error(response_stream: Any, status_code: int, message: str) -> None:
    response_stream.set_status_code(status_code)
    response_stream.set_header("Content-Type", "application/json")
    response_stream.write(json.dumps({"error": message}))


@awslambda.streamify_response
def lambda_handler(event: Dict[str, Any], context: Any, response_stream: Any) -> None:
    agent_arn = os.environ.get("AGENT_RUNTIME_ARN")
    if not agent_arn:
        _write_error(response_stream, 500, "AGENT_RUNTIME_ARN environment variable not set")
        return

    try:
        body = _parse_body(event)
    except json.JSONDecodeError as exc:
        _write_error(response_stream, 400, f"Invalid JSON in request: {exc}")
        return

    prompt = body.get("prompt")
    if not prompt:
        _write_error(response_stream, 400, "prompt is required in the request body")
        return

    session_id = body.get("session_id", f"session-{uuid.uuid4()}")
    content_type = body.get("content_type", "application/json")
    accept = body.get("accept", "text/event-stream")

    agent_core_client = boto3.client("bedrock-agentcore")
    payload = json.dumps({"prompt": prompt}).encode("utf-8")

    try:
        response = agent_core_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=payload,
            contentType=content_type,
            accept=accept,
        )
    except Exception as exc:
        _write_error(response_stream, 500, f"Error invoking agent: {exc}")
        return

    response_content_type = response.get("contentType", "text/event-stream")
    response_stream.set_status_code(200)
    response_stream.set_header("Content-Type", response_content_type)
    response_stream.set_header("X-Session-Id", session_id)

    if "text/event-stream" in response_content_type:
        for line in response["response"].iter_lines():
            if line:
                response_stream.write(line + b"\n")
        return

    if response_content_type == "application/json":
        chunks = []
        for chunk in response.get("response", []):
            chunks.append(chunk)
        response_stream.write(b"".join(chunks))
        return

    content = response.get("response", b"").read()
    if isinstance(content, bytes):
        response_stream.write(content)
    else:
        response_stream.write(str(content))
