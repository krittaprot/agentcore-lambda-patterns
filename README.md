# AWS Lambda Patterns for Amazon Bedrock AgentCore Runtime

![streaming-output-gid](https://github.com/user-attachments/assets/5af0e138-47f8-4938-85e7-50f69bef2939)

This repository contains two runnable AWS Lambda implementations for invoking Amazon Bedrock AgentCore Runtime agents, plus guidance for a third configuration that uses API Gateway (REST) response streaming.

Use these patterns when you want a client-facing API boundary and **don’t want to expose the AgentCore Runtime endpoint directly** (for example: clients can’t sign SigV4 requests, you need managed auth/throttling/WAF, or you need to normalize request headers/payloads).

## Overview

All options allow you to invoke Bedrock AgentCore agents, but they differ in how responses are delivered to clients:

| Feature | Option 1: API Gateway (Buffered) | Option 2: Lambda Function URL (Streaming) | Option 3: API Gateway (REST) Response Streaming |
|---------|------------------------------|------------------------------------------|----------------------------------------------|
| **Response Type** | Complete response (all at once) | Real-time streaming | Real-time streaming |
| **Architecture** | API Gateway → Lambda → Bedrock | Lambda Function URL → Lambda → Bedrock | API Gateway (REST, STREAM) → Lambda → Bedrock |
| **Use Case** | Standard REST APIs, batch processing | Real-time chat, long responses, lower cost | Streaming + API Gateway features (auth, custom domains, WAF) |
| **Latency (TTFB)** | Higher (waits for full response) | Lower (immediate chunks) | Lower (immediate chunks) |
| **Cost** | Medium (API Gateway + Lambda) | Lower (Lambda only) | Higher than Option 2 (API Gateway + Lambda) |
| **Streaming Support** | ❌ No | ✅ Yes | ✅ Yes (REST APIs only) |
| **API Gateway Features** | ✅ Available | ❌ Not applicable | ✅ Mostly available (some require buffering) |

Note: AgentCore Runtime also supports **direct** invocation (HTTP/SSE or WebSocket) with built-in session isolation and versioned endpoints. This repo focuses on Lambda-mediated patterns for cases where you want a separate client-facing API boundary.

AgentCore Runtime docs:
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-websocket.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html

## Why add Lambda/API Gateway instead of calling AgentCore directly?

You *can* invoke AgentCore Runtime directly from a backend service (and sometimes directly from clients). These orchestration layers exist because many real-world applications need a stable, production-ready API boundary in front of the agent.

What AgentCore Runtime already gives you out of the box:

- **Inbound auth:** IAM (SigV4) or OAuth 2.0.
- **Streaming options:** HTTP/SSE streaming responses and WebSocket (`/ws`).
- **Versioning:** immutable versions and stable endpoints (the `DEFAULT` endpoint tracks the latest).
- **Request header constraints:** only `Authorization` and headers prefixed with `X-Amzn-Bedrock-AgentCore-Runtime-Custom-` are forwarded to your container (up to 20 headers, 4KB each).
- **Session model:** isolated microVM sessions that can persist up to 8 hours; sessions terminate after 15 minutes of inactivity.


### Pros (why teams add the extra layers)

- **More auth front doors:** AgentCore supports IAM (SigV4) and OAuth 2.0; API Gateway can add other patterns like API keys, Cognito authorizers, and custom authorizers (plus usage plans) for a public API surface.
- **Protect the agent from spikes:** Throttling, quotas, and rate limits help prevent unexpected traffic bursts from causing downstream throttling and surprise spend.
- **Keep AWS credentials off clients:** Lambda can sign SigV4 requests to AgentCore so browsers/mobile apps don’t need IAM keys.
- **Header/payload translation:** If clients send standard headers that won’t be forwarded due to AgentCore’s header allowlist, Lambda/API Gateway can map them into `X-Amzn-Bedrock-AgentCore-Runtime-Custom-*` headers or move them into the body.
- **Cost/payload hygiene:** Validate requests, normalize payloads, and optionally redact PII before invoking the agent to avoid paying for obviously-bad requests.
- **Observability/audit:** Centralized logging/metrics/tracing at the edge (API Gateway/Lambda) makes it easier to answer “who called what, when, and how long did it take?”.
- **Security perimeter:** API Gateway + WAF + custom domains let you harden and brand the entrypoint without exposing the AgentCore Runtime endpoint directly.
- **Custom orchestration:** Enrich requests (RAG fetches, user context lookups) and perform payload transformations without changing clients or the agent.

### Cons (tradeoffs you should expect)

- **More moving parts:** Additional infrastructure to deploy, configure, monitor, and troubleshoot.
- **Higher cost/latency vs direct calls:** API Gateway adds cost, and extra hops can increase latency (especially for buffered responses).
- **Feature limitations with streaming:** Some API Gateway features require buffering and don’t work with response streaming (for example: caching, certain transformations).
- **Another trust boundary:** You now own input validation, auth decisions, and data handling at your edge.

### When direct calls are enough

- Internal, server-to-server use where IAM is already well-controlled.
- Prototypes or low-volume services where you don’t need custom auth, quotas, WAF, or payload transformation.

## Quick Start

### Prerequisites

1. **AWS CLI** installed and configured
2. **AWS SAM CLI** installed ([installation guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
3. **Bedrock AgentCore runtime** configured with **SigV4/IAM** inbound auth (these examples assume SigV4; AgentCore also supports OAuth 2.0 inbound auth)
4. Your agent's ARN (format: `arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/AGENT-ID`)

### Choose Your Option

#### Option 1: API Gateway + Lambda (Non-Streaming)

Best for: Standard REST APIs, when you need API Gateway features

```bash
cd option1-api-gateway
sam build
sam deploy --guided --parameter-overrides AgentRuntimeArn=YOUR_AGENT_ARN
```

See [option1-api-gateway/README.md](option1-api-gateway/README.md) for details.

#### Option 2: Lambda Function URL with Streaming

Best for: Real-time streaming, chat applications, lower costs

Notes:
- Function URL must use `InvokeMode: RESPONSE_STREAM` to enable streaming
- Response payloads can be up to 200 MB (request payloads still max 6 MB)
- After the first 6 MB, streaming throughput is capped at 2 MiB/s
- Node.js streaming uses `awslambda.streamifyResponse`; other runtimes need a custom runtime or Lambda Web Adapter
- If you need API Gateway features + streaming, see Option 3

```bash
cd option2-lambda-url
sam build
sam deploy --guided --parameter-overrides AgentRuntimeArn=YOUR_AGENT_ARN
```

See [option2-lambda-url/README.md](option2-lambda-url/README.md) for details.

#### Option 3: API Gateway (REST) Response Streaming + Lambda

Best for: Streaming responses while keeping API Gateway features (custom domains, authorizers, WAF, throttling, logging)

Notes:
- API Gateway response streaming is supported for **REST APIs** (not HTTP APIs)
- Enable streaming by setting the integration `responseTransferMode` to `STREAM` (supported for `AWS_PROXY` and `HTTP_PROXY` integrations)
- For Lambda integrations, API Gateway uses the Lambda `InvokeWithResponseStreaming` API (the integration URI includes `.../response-streaming-invocations`)
- Your Lambda must be streaming-enabled; in Node.js you typically use `awslambda.streamifyResponse` and wrap the stream with `awslambda.HttpResponseStream.from(responseStream, httpResponseMetadata)`
- Streams can run up to **15 minutes**, but idle timeouts apply (5 minutes Regional/Private, 30 seconds Edge-optimized)
- Some API Gateway features that require buffering don’t work with streaming (for example: caching, response transformations with VTL, content encoding)

References:
- AWS Lambda response streaming: https://aws.amazon.com/blogs/compute/introducing-aws-lambda-response-streaming/
- API Gateway response streaming overview: https://aws.amazon.com/blogs/compute/building-responsive-apis-with-amazon-api-gateway-response-streaming/
- API Gateway response transfer mode: https://docs.aws.amazon.com/apigateway/latest/developerguide/response-transfer-mode.html
- Lambda InvokeWithResponseStreaming API: https://docs.aws.amazon.com/lambda/latest/api/API_InvokeWithResponseStream.html

## Architecture Comparison

### Option 1: API Gateway + Lambda

```
┌────────┐     ┌─────────────┐     ┌────────┐     ┌──────────────┐
│ Client │────→│ API Gateway │────→│ Lambda │────→│   Bedrock    │
│ (curl) │     │   REST API  │     │        │     │  AgentCore   │
└────────┘     └─────────────┘     └────────┘     └──────────────┘
    ↑                                   │
    │          Waits for complete       │ Collects all
    │          response                 ↓ chunks
    └──────────────────────────────────────────────────────────────
                    Returns complete response
```

**Flow:**
1. Client sends request to API Gateway
2. API Gateway invokes Lambda
3. Lambda calls Bedrock AgentCore
4. Lambda collects ALL response chunks
5. Lambda returns complete response
6. API Gateway forwards to client
7. Client receives full response at once

### Option 2: Lambda Streaming

```
┌────────┐     ┌─────────────────────┐     ┌──────────────┐
│ Client │────→│  Lambda Function    │────→│   Bedrock    │
│ (curl) │     │  URL (streaming)    │     │  AgentCore   │
└────────┘     └─────────────────────┘     └──────────────┘
    ↑                   │
    │    Real-time      │ Streams chunks
    │    chunks         ↓ immediately
    └─────────────────────────────────────────────────────────
              Each chunk forwarded as it arrives
```

**Flow:**
1. Client sends request to Lambda Function URL
2. Lambda calls Bedrock AgentCore
3. As each chunk arrives from Bedrock:
   - Lambda immediately forwards it to client
4. Client sees responses in real-time

### Option 3: API Gateway Response Streaming (REST)

```
┌────────┐     ┌───────────────-┐     ┌────────┐     ┌──────────────┐
│ Client │────→│ API Gateway    │────→│ Lambda │────→│   Bedrock    │
│ (curl) │     │ REST API       │     │ (RS)   │     │  AgentCore   │
└────────┘     │ response STREAM│     └────────┘     └──────────────┘
    ↑          └───────────────-┘
    │     Real-time chunks
    └──────────────────────────────────────────────────────────────
```

**Flow:**
1. Client sends request to an API Gateway REST API endpoint
2. API Gateway uses an `AWS_PROXY`/`HTTP_PROXY` integration with `responseTransferMode: STREAM`
3. API Gateway invokes a streaming-enabled Lambda using the `.../response-streaming-invocations` integration URI
4. As Lambda writes to the response stream, API Gateway forwards chunks to the client immediately

Note: When streaming through API Gateway, Lambda must emit response metadata + a delimiter before the body. In Node.js, `awslambda.HttpResponseStream.from()` handles this for you.

**Securing Function URLs (production guidance):**
- Use `AWS_IAM` auth for Function URLs so requests must be SigV4-signed
- Function URLs do not support native JWT/Cognito authorizers; validate tokens in code or use API Gateway if you need managed auth
- For public apps, front the Function URL with CloudFront + WAF and use Origin Access Control (OAC) to sign requests
- Add a resource policy that restricts access to your CloudFront distribution and enforces `lambda:FunctionUrlAuthType`
- Use `NONE` only for demos or private, short-lived testing

## Authentication Requirements

### Bedrock AgentCore Agent

These examples assume your Bedrock AgentCore runtime is configured with **SigV4/IAM** inbound authentication.

AgentCore Runtime also supports **OAuth 2.0** inbound authentication. If your runtime is configured for OAuth, you’ll need to pass an `Authorization: Bearer ...` token and adjust the invocation path accordingly (this repo’s code currently demonstrates SigV4).

If you see this error:
```
Authorization method mismatch. The agent is configured for OAuth...
```

You need to reconfigure your agent to use SigV4 in the Bedrock console.

### Lambda IAM Permissions

Options 1–3 automatically configure the Lambda execution role with:

```json
{
  "Effect": "Allow",
  "Action": "bedrock-agentcore:InvokeAgentRuntime",
  "Resource": "arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/*"
}
```

## Common Issues

### Session ID Length Error

```
Invalid length for parameter runtimeSessionId, value: 16, valid min length: 33
```

**Solution:** Session IDs must be ≥33 characters. The provided implementations auto-generate valid session IDs using `session-{uuid}` format (44 chars).

### Authorization Method Mismatch

```
The agent is configured for OAuth but request used SigV4
```

**Solution:** Ensure your client uses the same inbound auth method your runtime is configured for. If this repo’s SigV4 examples don’t fit (because your runtime uses OAuth), either reconfigure the runtime to SigV4 or update the code to send OAuth bearer tokens.

Docs: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html

### Access Denied

```
User is not authorized to perform: bedrock-agentcore:InvokeAgentRuntime
```

**Solution:** Ensure the IAM policy Resource matches your agent ARN format:
- Correct: `arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/*`
- Wrong: `arn:aws:bedrock-agentcore:REGION:ACCOUNT:agent-runtime/*`

## Cost Comparison

### Option 1: API Gateway + Lambda

- API Gateway: $3.50 per million requests
- Lambda: $0.20 per 1M requests + $0.0000166667 per GB-second
- **Total for 1M requests (avg 5s, 512MB):** ~$4.12

### Option 2: Lambda Streaming Only

- Lambda: $0.20 per 1M requests + $0.0000166667 per GB-second
- **Total for 1M requests (avg 5s, 512MB):** ~$0.62

### Option 3: API Gateway Response Streaming + Lambda

- API Gateway: standard API invoke pricing (streamed responses are billed per 10 MB of response data, rounded up)
- Lambda: $0.20 per 1M requests + $0.0000166667 per GB-second
- Total depends on response size and duration; for small responses it’s close to Option 1, but delivers streaming UX

💡 **Option 2 is typically the cheapest** and provides true streaming without API Gateway. Use **Option 3** when you need API Gateway features *and* streaming.

## Deployment History

If you already deployed Option 1 and want to try Option 2:

1. **Keep Option 1 running:**
```bash
# Option 1 stack remains deployed
# API Gateway endpoint: (see the `sam deploy` output for the stack)
```

2. **Deploy Option 2 separately:**
```bash
cd option2-lambda-url
sam deploy --guided --parameter-overrides AgentRuntimeArn=YOUR_AGENT_ARN
# This creates a NEW stack with a different function
```

3. **Test both** and decide which to keep

4. **Clean up unwanted option:**
```bash
# Remove Option 1
aws cloudformation delete-stack --stack-name bedrock-agentcore-stack

# OR remove Option 2
aws cloudformation delete-stack --stack-name bedrock-streaming-stack
```

## File Structure

```
.
├── README.md                          # This file
├── requirements.txt                   # Python client dependencies
├── stream-client.py                   # Streaming client (strips SSE)
├── option1-api-gateway/               # Non-streaming implementation (API Gateway buffered)
│   ├── README.md                      # Option 1 documentation
│   ├── lambda_function.py             # Lambda handler (collects all chunks)
│   ├── template.yaml                  # SAM template with API Gateway
│   └── test_event.json                # Test event
├── option2-lambda-url/                # Streaming implementation (Lambda Function URL)
│   ├── README.md                      # Option 2 documentation
│   ├── index.js                       # Lambda handler (streams chunks)
│   ├── package.json                   # Node.js dependencies
│   ├── template.yaml                  # SAM template with Function URL
│   └── test_event.json                # Test event
└── option3-api-gateway-streaming/     # Streaming implementation (API Gateway REST response streaming)
    ├── README.md                      # Option 3 documentation
    ├── index.js                       # Lambda handler (API Gateway streaming compatible)
    ├── package.json                   # Node.js dependencies
    ├── template.yaml                  # SAM template with API Gateway REST + streaming
    └── test_event.json                # Test event
```

## Which Option Should I Choose?

Before adding Lambda/API Gateway, consider whether you can call **AgentCore Runtime directly**:
- Direct invocation supports HTTP/SSE and WebSocket (`/ws`) with IAM (SigV4) or OAuth 2.0.
- You must work within the request header allowlist (`X-Amzn-Bedrock-AgentCore-Runtime-Custom-*` and `Authorization`).

Docs:
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-service-contract.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-websocket.html
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html

### Choose Option 1 (API Gateway) if you need:
- Integration with existing API Gateway infrastructure
- API Gateway features (caching, throttling, custom domains, WAF)
- Standard REST API patterns
- Response size doesn't matter
- You don't need real-time feedback

### Choose Option 2 (Streaming) if you want:
- **Real-time streaming responses** ⭐
- Lower latency and better UX
- Lower costs (no API Gateway)
- Simpler architecture
- Chat or conversational interfaces
- Long-running agent responses

### Choose Option 3 (API Gateway Response Streaming) if you need:
- **Real-time streaming** while still using API Gateway features (authorizers, custom domains, WAF, throttling)
- A REST API (response streaming is not supported for HTTP APIs)
- To accept streaming tradeoffs (some features require buffering, like caching and response transforms)

**Recommendation:** Start with **Option 2 (Streaming)** for best UX and lowest cost. Choose **Option 3** when you need API Gateway features *and* streaming. Use **Option 1** when you don’t need streaming.

## Support

For issues or questions:
- Check the README in each option folder
- Review AWS Lambda documentation: https://docs.aws.amazon.com/lambda/
- Review Bedrock AgentCore documentation: https://docs.aws.amazon.com/bedrock/

## License

This project is provided as-is for educational and development purposes.
