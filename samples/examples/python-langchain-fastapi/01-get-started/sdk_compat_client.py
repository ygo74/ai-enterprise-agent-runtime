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


def test_openai_responses(base_url: str, model: str, prompt: str, route_key: str, stream: bool = False) -> bool:
    try:
        from openai import OpenAI
    except Exception as ex:
        _print_result("OpenAI SDK import", False, f"Unable to import openai package: {ex}")
        return False

    endpoint = f"{base_url.rstrip('/')}/v1"
    api_key = os.getenv("OPENAI_API_KEY", "dummy-local-key")

    if stream:
        title = "OpenAI SDK -> /v1/responses (stream=True)"
        try:
            client = OpenAI(api_key=api_key, base_url=endpoint)
            events = client.responses.create(
                model=model,
                input=prompt,
                stream=True,
                metadata={"request_id": "compat-openai-resp-stream-001", "route_key": route_key},
            )

            deltas: list[str] = []
            saw_completed = False
            for event in events:
                event_type = getattr(event, "type", None)
                if event_type == "response.output_text.delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        deltas.append(delta)
                elif event_type == "response.completed":
                    saw_completed = True

            ok = len(deltas) > 0 and saw_completed
            _print_result(
                title,
                ok,
                f"chunks_received={len(deltas)}\nsaw_completed={saw_completed}\ntext={''.join(deltas)}",
            )
            return ok
        except Exception as ex:
            _print_result(title, False, f"Request failed: {ex}")
            return False

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


def test_openai_chat_completions(base_url: str, model: str, prompt: str, route_key: str, stream: bool = False) -> bool:
    try:
        from openai import OpenAI
    except Exception as ex:
        _print_result("OpenAI SDK import", False, f"Unable to import openai package: {ex}")
        return False

    endpoint = f"{base_url.rstrip('/')}/v1"
    api_key = os.getenv("OPENAI_API_KEY", "dummy-local-key")

    if stream:
        title = "OpenAI SDK -> /v1/chat/completions (stream=True)"
        try:
            client = OpenAI(api_key=api_key, base_url=endpoint)
            events = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
                extra_body={"metadata": {"request_id": "compat-openai-chat-stream-001", "route_key": route_key}},
            )

            chunks: list[str] = []
            saw_finish_reason = False
            for chunk in events:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    chunks.append(delta)
                if chunk.choices and chunk.choices[0].finish_reason:
                    saw_finish_reason = True

            ok = len(chunks) > 0 and saw_finish_reason
            _print_result(
                title,
                ok,
                f"chunks_received={len(chunks)}\nsaw_finish_reason={saw_finish_reason}\ntext={''.join(chunks)}",
            )
            return ok
        except Exception as ex:
            _print_result(title, False, f"Request failed: {ex}")
            return False

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


def test_anthropic_messages(base_url: str, model: str, prompt: str, stream: bool = False) -> bool:
    try:
        import anthropic
    except Exception as ex:
        _print_result("Anthropic SDK import", False, f"Unable to import anthropic package: {ex}")
        return False

    # Anthropic SDK targets /v1/messages from base_url root.
    endpoint = base_url.rstrip("/")
    api_key = os.getenv("ANTHROPIC_API_KEY", "dummy-local-key")

    if stream:
        title = "Anthropic SDK -> /v1/messages (stream=True)"
        try:
            client = anthropic.Anthropic(api_key=api_key, base_url=endpoint)
            deltas: list[str] = []
            saw_message_stop = False
            with client.messages.stream(
                model=model,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            ) as message_stream:
                for event in message_stream:
                    event_type = getattr(event, "type", None)
                    if event_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        text = getattr(delta, "text", None) if delta else None
                        if text:
                            deltas.append(text)
                    elif event_type == "message_stop":
                        saw_message_stop = True

            ok = len(deltas) > 0 and saw_message_stop
            _print_result(
                title,
                ok,
                f"chunks_received={len(deltas)}\nsaw_message_stop={saw_message_stop}\ntext={''.join(deltas)}",
            )
            return ok
        except Exception as ex:
            _print_result(
                title,
                False,
                "Request failed. Ensure endpoint /v1/messages is enabled in add_ai_endpoints(...).\n"
                f"error={ex}",
            )
            return False

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
    parser.add_argument(
        "--test-openai-responses",
        action="store_true",
        help="Run only the OpenAI SDK -> /v1/responses check.",
    )
    parser.add_argument(
        "--test-openai-chat-completions",
        action="store_true",
        help="Run only the OpenAI SDK -> /v1/chat/completions check.",
    )
    parser.add_argument(
        "--test-anthropic-messages",
        action="store_true",
        help="Run only the Anthropic SDK -> /v1/messages check.",
    )
    parser.add_argument(
        "--enable-stream",
        action="store_true",
        help="Run the selected check(s) with stream=True instead of a single blocking response.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("Running SDK compatibility checks against local endpoint...")
    print(f"base_url={args.base_url}")

    selected = {
        "openai_responses": args.test_openai_responses,
        "openai_chat_completions": args.test_openai_chat_completions,
        "anthropic_messages": args.test_anthropic_messages,
    }

    if not any(selected.values()):
        # No explicit --test-* flag: keep the previous "run everything" default.
        selected = {
            "openai_responses": True,
            "openai_chat_completions": True,
            "anthropic_messages": not args.skip_anthropic,
        }

    results = []

    if selected["openai_responses"]:
        results.append(
            test_openai_responses(
                args.base_url, args.openai_model, args.prompt, args.route_key, stream=args.enable_stream
            )
        )

    if selected["openai_chat_completions"]:
        results.append(
            test_openai_chat_completions(
                args.base_url, args.openai_model, args.prompt, args.route_key, stream=args.enable_stream
            )
        )

    if selected["anthropic_messages"]:
        results.append(
            test_anthropic_messages(args.base_url, args.anthropic_model, args.prompt, stream=args.enable_stream)
        )

    if not results:
        print("No checks selected to run.")
        return 1

    ok_count = sum(1 for item in results if item)
    print(f"Summary: {ok_count}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
