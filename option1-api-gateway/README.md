# Option 1: API Gateway + Lambda (Non-Streaming)

This implementation uses **API Gateway REST API** with a traditional Lambda function. The Lambda collects all response chunks from Bedrock AgentCore before returning the complete response to the client.

## Architecture

```
Client (curl) → API Gateway → Lambda → Bedrock AgentCore
                                ↓
                         Collect all chunks
                                ↓
Client ← Complete response ← Lambda
```

## Characteristics

✅ **Pros:**
- Simple and familiar architecture
- Works with API Gateway REST API
- Easy to integrate with existing API Gateway setups
- Supports API Gateway features (throttling, caching, custom domains)

❌ **Cons:**
- **No real-time streaming** - client waits for complete response
- Higher latency for long responses
- Must wait for entire agent response before client sees anything

## Setup

### 1. Deploy the stack

```bash
cd option1-api-gateway
sam build
sam deploy --guided --parameter-overrides AgentRuntimeArn=YOUR_AGENT_ARN
```

### 2. Required IAM Permissions

The Lambda execution role automatically gets:
```json
{
  "Effect": "Allow",
  "Action": "bedrock-agentcore:InvokeAgentRuntime",
  "Resource": "arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/*"
}
```

### 3. Environment Variables

- `AGENT_RUNTIME_ARN`: Set via CloudFormation parameter during deployment

## Usage

### Invoke via API Gateway

```bash
curl -X POST https://YOUR-API-ID.execute-api.REGION.amazonaws.com/Prod/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello, how can you help me today?"}'
```

### With custom session ID

```bash
curl -X POST https://YOUR-API-ID.execute-api.REGION.amazonaws.com/Prod/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the weather today?",
    "session_id": "my-custom-session-id-that-is-at-least-33-chars"
  }'
```

## Response Format

```json
{
  "session_id": "session-xxxx-xxxx-xxxx",
  "response": "Complete agent response here...",
  "content_type": "text/event-stream"
}
```

## Clean Up

```bash
cd option1-api-gateway
sam delete
```

Or via CloudFormation:
```bash
aws cloudformation delete-stack --stack-name bedrock-agentcore-stack
```

## Files

- `lambda_function.py` - Lambda handler that collects all chunks before responding
- `template.yaml` - SAM template with API Gateway + Lambda
- `test_event.json` - Sample test event for Lambda console
- `README.md` - This file
