import boto3
import json
import os
import uuid
from typing import Dict, Any


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for invoking Bedrock AgentCore Runtime.

    Expected environment variables:
    - AGENT_RUNTIME_ARN: The ARN of the Bedrock AgentCore agent

    Expected event structure:
    {
        "prompt": "Your prompt text here",
        "session_id": "optional-session-id",  # Optional, will be generated if not provided
        "content_type": "application/json",   # Optional
        "accept": "application/json"          # Optional
    }
    """
    try:
        # Get agent ARN from environment variable
        agent_arn = os.environ.get('AGENT_RUNTIME_ARN')
        if not agent_arn:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'AGENT_RUNTIME_ARN environment variable not set'})
            }

        # Parse the event - support both direct invocation and API Gateway
        if isinstance(event.get('body'), str):
            # API Gateway format
            body = json.loads(event['body'])
        else:
            # Direct invocation
            body = event

        # Extract parameters
        prompt = body.get('prompt')
        if not prompt:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'prompt is required in the request body'})
            }

        # AWS Bedrock AgentCore requires session ID to be at least 33 characters
        session_id = body.get('session_id', f"session-{uuid.uuid4()}")
        content_type = body.get('content_type', 'application/json')
        accept = body.get('accept', 'application/json')

        # Initialize the Bedrock AgentCore client
        agent_core_client = boto3.client('bedrock-agentcore')

        # Prepare the payload
        payload = json.dumps({"prompt": prompt}).encode()

        # Invoke the agent
        response = agent_core_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=payload,
            contentType=content_type,
            accept=accept
        )

        # Process the response based on content type
        response_content_type = response.get("contentType", "")

        if "text/event-stream" in response_content_type:
            # Handle streaming response
            content = []
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                    content.append(line)

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'session_id': session_id,
                    'response': '\n'.join(content),
                    'content_type': response_content_type
                })
            }

        elif response.get("contentType") == "application/json":
            # Handle standard JSON response
            content = []
            for chunk in response.get("response", []):
                content.append(chunk.decode('utf-8'))

            parsed_response = json.loads(''.join(content))

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'session_id': session_id,
                    'response': parsed_response,
                    'content_type': response_content_type
                })
            }

        else:
            # Handle other content types
            content = response.get("response", b'').read()

            return {
                'statusCode': 200,
                'body': json.dumps({
                    'session_id': session_id,
                    'response': content.decode('utf-8') if isinstance(content, bytes) else str(content),
                    'content_type': response_content_type
                })
            }

    except json.JSONDecodeError as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': f'Invalid JSON in request: {str(e)}'})
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Error invoking agent: {str(e)}'})
        }
