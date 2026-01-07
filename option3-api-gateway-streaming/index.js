const { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } = require("@aws-sdk/client-bedrock-agentcore");
const crypto = require("node:crypto");
const { pipeline } = require("node:stream/promises");

const client = new BedrockAgentCoreClient({});

const parseBody = (event) => {
  if (event && typeof event === "object" && "body" in event) {
    let body = event.body || "";
    if (event.isBase64Encoded && body) {
      body = Buffer.from(body, "base64").toString("utf-8");
    }
    return body ? JSON.parse(body) : {};
  }
  return event && typeof event === "object" ? event : {};
};

const writeError = (responseStream, statusCode, message) => {
  const httpResponseMetadata = {
    statusCode,
    headers: {
      "Content-Type": "application/json",
    },
  };

  const wrappedStream = awslambda.HttpResponseStream.from(
    responseStream,
    httpResponseMetadata
  );

  wrappedStream.write(JSON.stringify({ error: message }));
  wrappedStream.end();
};

const writeSdkStream = async (sdkStream, responseStream) => {
  if (!sdkStream) {
    responseStream.end();
    return;
  }

  if (typeof sdkStream.pipe === "function") {
    await pipeline(sdkStream, responseStream);
    return;
  }

  if (typeof sdkStream[Symbol.asyncIterator] === "function") {
    for await (const chunk of sdkStream) {
      responseStream.write(chunk);
    }
    responseStream.end();
    return;
  }

  if (typeof sdkStream.transformToByteArray === "function") {
    const bytes = await sdkStream.transformToByteArray();
    responseStream.write(Buffer.from(bytes));
    responseStream.end();
    return;
  }

  if (typeof sdkStream.transformToString === "function") {
    const text = await sdkStream.transformToString();
    responseStream.write(text);
    responseStream.end();
    return;
  }

  responseStream.end();
};

exports.handler = awslambda.streamifyResponse(async (event, responseStream, context) => {
  const agentArn = process.env.AGENT_RUNTIME_ARN;
  if (!agentArn) {
    writeError(responseStream, 500, "AGENT_RUNTIME_ARN environment variable not set");
    return;
  }

  let body;
  try {
    body = parseBody(event);
  } catch (error) {
    writeError(responseStream, 400, `Invalid JSON in request: ${error}`);
    return;
  }

  const prompt = body.prompt;
  if (!prompt) {
    writeError(responseStream, 400, "prompt is required in the request body");
    return;
  }

  const sessionId = body.session_id || `session-${crypto.randomUUID()}`;
  const contentType = body.content_type || "application/json";
  const accept = body.accept || "text/event-stream";

  let response;
  try {
    const command = new InvokeAgentRuntimeCommand({
      agentRuntimeArn: agentArn,
      runtimeSessionId: sessionId,
      payload: Buffer.from(JSON.stringify({ prompt }), "utf-8"),
      contentType,
      accept,
    });
    response = await client.send(command);
  } catch (error) {
    writeError(responseStream, 500, `Error invoking agent: ${error}`);
    return;
  }

  const responseContentType = response.contentType || "text/event-stream";
  const httpResponseMetadata = {
    statusCode: 200,
    headers: {
      "Content-Type": responseContentType,
      "X-Session-Id": sessionId,
    },
  };

  // Wrap the response stream for API Gateway compatibility
  const wrappedStream = awslambda.HttpResponseStream.from(
    responseStream,
    httpResponseMetadata
  );

  try {
    await writeSdkStream(response.response, wrappedStream);
  } catch (error) {
    // If we've already started streaming, we can't send a proper error response
    // Just log and close the stream
    console.error("Error streaming response:", error);
    wrappedStream.end();
  }
});