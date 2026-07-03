"""
Anthropic + OpenAI wrappers — observe-fails-open.

Usage:
    from agentreceipts import wrap

    client = wrap(anthropic.Anthropic())
    # or
    client = wrap(openai.OpenAI())

    resp = client.messages.create(...)  # or client.chat.completions.create(...)
    # Receipt emitted automatically; host call never broken by capture failure.
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from ._receipt import emit_observation
from ._context import get_run


def _sha256_anchor(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _anchor_messages(messages: list[dict]) -> str:
    """Hash the full messages list — anchor-not-content."""
    import json
    return "sha256:" + hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()


class _AnthropicMessagesWrapper:
    def __init__(self, messages_api: Any, config: dict) -> None:
        self._api = messages_api
        self._config = config

    def create(self, **kwargs: Any) -> Any:
        run = get_run()
        call_id = "ar_call_" + uuid.uuid4().hex[:12]
        prompt_anchor = _anchor_messages(kwargs.get("messages", []))
        model = kwargs.get("model", "unknown")

        try:
            response = self._api.create(**kwargs)
        except Exception as host_err:
            try:
                emit_observation(
                    event_type="obs.llm.call.error.v1",
                    payload={
                        "call_id": call_id,
                        "provider": "anthropic",
                        "model": model,
                        "prompt_anchor": prompt_anchor,
                        "error": type(host_err).__name__,
                        "run_id": run["run_id"] if run else None,
                        **self._config,
                    },
                    **{k: v for k, v in self._config.items() if k in ("key_path", "key_id", "out_dir")},
                )
            except Exception:
                pass
            raise

        try:
            content = response.content[0].text if response.content else ""
            output_anchor = _sha256_anchor(content)
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
            emit_observation(
                event_type="obs.llm.call.v1",
                payload={
                    "call_id": call_id,
                    "provider": "anthropic",
                    "model": model,
                    "stop_reason": response.stop_reason,
                    "prompt_anchor": prompt_anchor,
                    "output_anchor": output_anchor,
                    "usage": usage,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "run_id": run["run_id"] if run else None,
                },
                **{k: v for k, v in self._config.items() if k in ("key_path", "key_id", "out_dir")},
            )
        except Exception:
            pass  # capture failure never breaks host call

        return response


class _AnthropicClientWrapper:
    def __init__(self, client: Any, config: dict) -> None:
        self._client = client
        self._config = config
        self.messages = _AnthropicMessagesWrapper(client.messages, config)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class _OpenAICompletionsWrapper:
    def __init__(self, completions_api: Any, config: dict) -> None:
        self._api = completions_api
        self._config = config

    def create(self, **kwargs: Any) -> Any:
        run = get_run()
        call_id = "ar_call_" + uuid.uuid4().hex[:12]
        prompt_anchor = _anchor_messages(kwargs.get("messages", []))
        model = kwargs.get("model", "unknown")

        try:
            response = self._api.create(**kwargs)
        except Exception as host_err:
            try:
                emit_observation(
                    event_type="obs.llm.call.error.v1",
                    payload={
                        "call_id": call_id,
                        "provider": "openai",
                        "model": model,
                        "prompt_anchor": prompt_anchor,
                        "error": type(host_err).__name__,
                        "run_id": run["run_id"] if run else None,
                    },
                    **{k: v for k, v in self._config.items() if k in ("key_path", "key_id", "out_dir")},
                )
            except Exception:
                pass
            raise

        try:
            content = response.choices[0].message.content if response.choices else ""
            output_anchor = _sha256_anchor(content or "")
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }
            emit_observation(
                event_type="obs.llm.call.v1",
                payload={
                    "call_id": call_id,
                    "provider": "openai",
                    "model": model,
                    "finish_reason": response.choices[0].finish_reason if response.choices else None,
                    "prompt_anchor": prompt_anchor,
                    "output_anchor": output_anchor,
                    "usage": usage,
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "run_id": run["run_id"] if run else None,
                },
                **{k: v for k, v in self._config.items() if k in ("key_path", "key_id", "out_dir")},
            )
        except Exception:
            pass

        return response


class _OpenAIChatWrapper:
    def __init__(self, chat_api: Any, config: dict) -> None:
        self._api = chat_api
        self._config = config
        self.completions = _OpenAICompletionsWrapper(chat_api.completions, config)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._api, name)


class _OpenAIClientWrapper:
    def __init__(self, client: Any, config: dict) -> None:
        self._client = client
        self._config = config
        self.chat = _OpenAIChatWrapper(client.chat, config)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def wrap_client(client: Any, config: dict) -> Any:
    """Detect client type and return the appropriate wrapper."""
    cls_name = type(client).__name__
    module = type(client).__module__

    if "anthropic" in module or cls_name in ("Anthropic", "AsyncAnthropic"):
        return _AnthropicClientWrapper(client, config)
    if "openai" in module or cls_name in ("OpenAI", "AsyncOpenAI"):
        return _OpenAIClientWrapper(client, config)

    raise TypeError(f"Unsupported client type: {module}.{cls_name}. Pass an Anthropic or OpenAI client.")
