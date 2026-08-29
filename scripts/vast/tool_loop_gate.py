#!/usr/bin/env python3
"""Run a private two-step OpenAI-compatible tool-loop gate."""

import argparse
import json
import urllib.request


def post(base_url: str, api_key: str, body: dict) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:17070")
    parser.add_argument("--api-key-file", required=True)
    parser.add_argument("--proof", default="quality-proof-49172443")
    args = parser.parse_args()

    api_key = open(args.api_key_file, encoding="utf-8").read().strip()
    messages = [
        {
            "role": "user",
            "content": (
                "Use the read_file tool to read /tmp/quality-proof.txt. "
                "Do not guess its contents."
            ),
        }
    ]
    tool = {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    }
    common = {
        "model": "qwen3.8-q3",
        "temperature": 1,
        "max_tokens": 1024,
        "tools": [tool],
        "tool_choice": "auto",
    }
    first = post(args.base_url, api_key, {**common, "messages": messages})
    assistant = first["choices"][0]["message"]
    calls = assistant.get("tool_calls") or []
    if len(calls) != 1 or calls[0]["function"]["name"] != "read_file":
        raise SystemExit("Expected one read_file tool call")
    arguments = json.loads(calls[0]["function"]["arguments"])
    if arguments != {"path": "/tmp/quality-proof.txt"}:
        raise SystemExit(f"Unexpected tool arguments: {arguments!r}")

    messages.extend(
        [
            assistant,
            {
                "role": "tool",
                "tool_call_id": calls[0]["id"],
                "content": args.proof,
            },
        ]
    )
    second = post(args.base_url, api_key, {**common, "messages": messages})
    final_message = second["choices"][0]["message"]
    final_text = final_message.get("content") or ""
    if args.proof not in final_text:
        raise SystemExit("Final answer did not contain the tool result")

    print(
        json.dumps(
            {
                "status": "ok",
                "tool_name": calls[0]["function"]["name"],
                "tool_arguments": arguments,
                "first_finish_reason": first["choices"][0]["finish_reason"],
                "second_finish_reason": second["choices"][0]["finish_reason"],
                "first_timings": first.get("timings"),
                "second_timings": second.get("timings"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
