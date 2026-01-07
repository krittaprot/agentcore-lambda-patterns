# Option 2: Lambda Function URL with Streaming

This implementation uses a **Lambda Function URL** with **response streaming**. The Node.js handler forwards Bedrock AgentCore chunks to the client as they arrive, enabling real-time output.

## Architecture

```
Client (curl) -> Lambda Function URL -> Bedrock AgentCore
                    ^
                    | Streams chunks immediately
```

## Characteristics

✅ **Pros:**
- Real-time streaming for long responses
- Lower latency for the first tokens
- Lower cost (no API Gateway)
- Simpler architecture

❌ **Cons:**
- Function URLs lack API Gateway features
- Auth must be handled via IAM or in-code logic

## Setup

### 1. Deploy the stack

```bash
cd option2-lambda-url
sam build
sam deploy --guided --parameter-overrides AgentRuntimeArn=YOUR_AGENT_ARN
```

Note: `sam build` installs dependencies from `package.json`.

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

### Invoke via Function URL (streaming)

```bash
curl -X POST YOUR_FUNCTION_URL --no-buffer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me a story"}'
```

### With custom session ID

```bash
curl -X POST YOUR_FUNCTION_URL --no-buffer \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the weather today?",
    "session_id": "my-custom-session-id-that-is-at-least-33-chars"
  }'
```

## Response Behavior

- Responses are streamed as they arrive from Bedrock AgentCore.
- The function sets `Content-Type: text/event-stream` by default.
- The session ID is returned in the `X-Session-Id` response header.

## Clean Up

```bash
cd option2-lambda-url
sam delete
```

Or via CloudFormation:
```bash
aws cloudformation delete-stack --stack-name bedrock-streaming-stack
```

## Files

- `index.js` - Lambda handler that streams chunks immediately
- `package.json` - Node.js dependencies (AWS SDK v3)
- `template.yaml` - SAM template with Function URL response streaming
- `test_event.json` - Sample test event for Lambda console
- `README.md` - This file
