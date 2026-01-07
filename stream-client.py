import argparse
import json
import os
import sys
from typing import Iterable
import requests
from dotenv import load_dotenv

load_dotenv()  # reads variables from a .env file and sets them in os.environ

def iter_sse_data(lines: Iterable[bytes]) -> Iterable[str]:
    for raw_line in lines:
        if not raw_line:
            continue
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("data:"):
            yield line[5:].lstrip()


DEFAULT_URL = os.environ.get("AGENTCORE_STREAM_URL", "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream SSE responses from a streaming endpoint.")
    parser.add_argument(
        "url",
        nargs="?",
        default=DEFAULT_URL,
        help="Streaming endpoint URL (API Gateway or Function URL). You can also set AGENTCORE_STREAM_URL.",
    )
    parser.add_argument("prompt", help="Prompt text")
    parser.add_argument("--session-id", dest="session_id", help="Optional session id")
    parser.add_argument(
        "--accept",
        default="text/event-stream",
        help="Accept header (default: text/event-stream)",
    )
    args = parser.parse_args()

    if not args.url:
        raise SystemExit("No URL provided. Set DEFAULT_URL or pass the URL argument.")

    payload = {"prompt": args.prompt}
    if args.session_id:
        payload["session_id"] = args.session_id

    with requests.post(
        args.url,
        headers={"Content-Type": "application/json", "Accept": args.accept},
        data=json.dumps(payload),
        stream=True,
        timeout=300,
    ) as response:
        response.raise_for_status()
        for chunk in iter_sse_data(response.iter_lines()):
            if not chunk:
                continue
            try:
                text = json.loads(chunk)
            except json.JSONDecodeError:
                text = chunk
            sys.stdout.write(text)
            sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
