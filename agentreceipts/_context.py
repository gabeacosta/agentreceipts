"""Active run context — thread/async-safe via contextvars."""

from contextvars import ContextVar
from typing import Any

_active_run: ContextVar[dict | None] = ContextVar("_active_run", default=None)


def set_run(run_id: str, metadata: dict[str, Any]) -> None:
    _active_run.set({"run_id": run_id, "metadata": metadata})


def get_run() -> dict | None:
    return _active_run.get()


def clear_run() -> None:
    _active_run.set(None)
