# Option 3: API Gateway REST Response Streaming + Lambda

This implementation combines **API Gateway REST API** with **Lambda response streaming**. You get real-time streaming responses while keeping API Gateway features like custom domains, authorizers, WAF, and throttling.

## Architecture

```
Client (curl) -> API Gateway REST API -> Lambda (streaming) -> Bedrock AgentCore
                          ^
                          | Streams chunks via responseTransferMode: STREAM
```

## Characteristics

✅ **Pros:**
- Real-time streaming for long responses
- Keep API Gateway features (auth, custom domains, WAF, throttling, logging)
- Up to 15-minute timeouts for streaming responses
- Works with existing API Gateway infrastructure

❌ **Cons:**
- Higher cost than Function URLs (API Gateway + Lambda)
- Some API Gateway features don't work with streaming (caching, response transforms, content encoding)
- Only supported for REST APIs (not HTTP APIs)
- More complex setup than Function URLs

## Setup

### 1. Deploy the stack

```bash
cd option3-api-gateway-streaming
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

API Gateway gets permissions to invoke Lambda with response streaming:
```json
{
  "Effect": "Allow",
  "Action": [
    "lambda:InvokeFunction",
    "lambda:InvokeWithResponseStream"
  ],
  "Resource": "LAMBDA_FUNCTION_ARN"
}
```

### 3. Environment Variables

- `AGENT_RUNTIME_ARN`: Set via CloudFormation parameter during deployment

## Key Configuration Details

### API Gateway Integration
- **Integration Type**: `AWS_PROXY`
- **responseTransferMode**: `STREAM` 
- **Integration URI**: Uses `.../response-streaming-invocations` endpoint
- **Timeout**: Up to 15 minutes (900,000ms)

### Lambda Handler
- Uses `awslambda.streamifyResponse` for streaming
- Wraps response stream with `awslambda.HttpResponseStream.from()` for API Gateway compatibility
- Handles HTTP response metadata (status code, headers) before streaming body

## Usage

### Invoke via API Gateway (streaming)

```bash
curl -X POST YOUR_API_GATEWAY_URL --no-buffer \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me a story"}'
```

### With custom session ID

```bash
curl -X POST YOUR_API_GATEWAY_URL --no-buffer \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is the weather today?",
    "session_id": "my-custom-session-id-that-is-at-least-33-chars"
  }'
```

## Response Behavior

- Responses are streamed as they arrive from Bedrock AgentCore
- API Gateway forwards chunks immediately (no buffering)
- The function sets `Content-Type: text/event-stream` by default
- Session ID is returned in the `X-Session-Id` response header
- CORS headers are included for browser compatibility

## Limitations with Streaming

When `responseTransferMode: STREAM` is enabled, these API Gateway features are **not supported**:
- Response caching
- Response transformations with VTL
- Content encoding (gzip/compress in API Gateway)

## Timeouts and Limits

- **Maximum streaming time**: 15 minutes
- **Idle timeout**: 5 minutes (Regional/Private), 30 seconds (Edge-optimized)
- **Bandwidth**: First 10MB unrestricted, then 2MB/s throttling
- **Request payload**: Still limited to 10MB (same as non-streaming)

## Clean Up

```bash
cd option3-api-gateway-streaming
sam delete
```

Or via CloudFormation:
```bash
aws cloudformation delete-stack --stack-name bedrock-agentcore-streaming-api-stack
```

## Files

- `index.js` - Lambda handler with API Gateway streaming compatibility
- `package.json` - Node.js dependencies (AWS SDK v3)
- `template.yaml` - SAM template with API Gateway REST + streaming configuration
- `test_event.json` - Sample test event for Lambda console
- `README.md` - This file

## When to Use Option 3

Choose this option when you need:
- **Real-time streaming responses** AND API Gateway features
- Custom domains, authorizers, WAF protection, or request throttling
- Integration with existing API Gateway infrastructure
- CORS support for browser clients
- REST API patterns (OpenAPI/Swagger documentation)

If you only need streaming without API Gateway features, Option 2 (Function URLs) is simpler and cheaper.