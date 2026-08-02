from __future__ import annotations

import argparse
import json
import os
from typing import Any

from env_loader import ensure_env_loaded

ensure_env_loaded()


def _pretty(data: Any) -> str:
    if hasattr(data, "model_dump"):
        try:
            return json.dumps(data.model_dump(), ensure_ascii=True, indent=2)
        except Exception:
            pass

    try:
        return json.dumps(data, ensure_ascii=True, indent=2)
    except Exception:
        return str(data)


def _print_result(title: str, ok: bool, details: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"\n[{status}] {title}\n{details}\n")


def test_openai_responses(base_url: str, model: str, prompt: str, route_key: str) -> bool:
    try:
        from openai import OpenAI
    except Exception as ex:
        _print_result("OpenAI SDK import", False, f"Unable to import openai package: {ex}")
        return False

    endpoint = f"{base_url.rstrip('/')}/v1"
    api_key = os.getenv("OPENAI_API_KEY", "dummy-local-key")

    try:
        client = OpenAI(api_key=api_key, base_url=endpoint)
        raw = client.responses.with_raw_response.create(
            model=model,
            input=prompt,
            metadata={"request_id": "compat-openai-resp-001", "route_key": route_key},
        )
        payload = raw.parse()
        _print_result(
            "OpenAI SDK -> /v1/responses",
            raw.status_code == 200,
            f"status_code={raw.status_code}\nresponse={_pretty(payload)}",
        )
        return raw.status_code == 200
    except Exception as ex:
        _print_result("OpenAI SDK -> /v1/responses", False, f"Request failed: {ex}")
        return False


def test_openai_chat_completions(base_url: str, model: str, prompt: str, route_key: str) -> bool:
    try:
        from openai import OpenAI
    except Exception as ex:
        _print_result("OpenAI SDK import", False, f"Unable to import openai package: {ex}")
        return False

    endpoint = f"{base_url.rstrip('/')}/v1"
    api_key = os.getenv("OPENAI_API_KEY", "dummy-local-key")

    try:
        client = OpenAI(api_key=api_key, base_url=endpoint)
        raw = client.chat.completions.with_raw_response.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"metadata": {"request_id": "compat-openai-chat-001", "route_key": route_key}},
        )
        payload = raw.parse()
        _print_result(
            "OpenAI SDK -> /v1/chat/completions",
            raw.status_code == 200,
            f"status_code={raw.status_code}\nresponse={_pretty(payload)}",
        )
        return raw.status_code == 200
    except Exception as ex:
        _print_result("OpenAI SDK -> /v1/chat/completions", False, f"Request failed: {ex}")
        return False


def test_anthropic_messages(base_url: str, model: str, prompt: str) -> bool:
    try:
        import anthropic
    except Exception as ex:
        _print_result("Anthropic SDK import", False, f"Unable to import anthropic package: {ex}")
        return False

    # Anthropic SDK targets /v1/messages from base_url root.
    endpoint = base_url.rstrip("/")
    api_key = os.getenv("ANTHROPIC_API_KEY", "dummy-local-key")

    try:
        client = anthropic.Anthropic(api_key=api_key, base_url=endpoint)
        raw = client.messages.with_raw_response.create(
            model=model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        payload = raw.parse()
        _print_result(
            "Anthropic SDK -> /v1/messages",
            raw.http_response.status_code == 200,
            f"status_code={raw.http_response.status_code}\nresponse={_pretty(payload)}",
        )
        return raw.http_response.status_code == 200
    except Exception as ex:
        _print_result(
            "Anthropic SDK -> /v1/messages",
            False,
            "Request failed. Ensure endpoint /v1/messages is enabled in add_ai_endpoints(...).\n"
            f"error={ex}",
        )
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SDK compatibility client for local AI endpoints.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001", help="Base URL of the local API.")
    parser.add_argument("--openai-model", default=os.getenv("OPENAI_MODEL", "gpt-5-chat"))
    parser.add_argument("--anthropic-model", default=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"))
    parser.add_argument("--route-key", default="ai-solution-architect")
    parser.add_argument(
        "--prompt",
        default="Design an enterprise AI architecture for RAG with governance, observability, and cost controls.",
    )
    parser.add_argument(
        "--skip-anthropic",
        action="store_true",
        help="Skip Anthropic SDK test if /v1/messages is not enabled.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("Running SDK compatibility checks against local endpoint...")
    print(f"base_url={args.base_url}")

    results = [
        test_openai_responses(args.base_url, args.openai_model, args.prompt, args.route_key),
        test_openai_chat_completions(args.base_url, args.openai_model, args.prompt, args.route_key),
    ]

    if not args.skip_anthropic:
        results.append(test_anthropic_messages(args.base_url, args.anthropic_model, args.prompt))

    ok_count = sum(1 for item in results if item)
    print(f"Summary: {ok_count}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
