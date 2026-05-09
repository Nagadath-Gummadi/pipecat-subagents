#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Decorator for marking agent methods as task handlers."""

from collections.abc import Callable


def task(*, name: str):
    """Mark an agent method as a task handler.

    Decorated methods are automatically collected by ``BaseAgent`` at
    initialization and dispatched when matching task requests arrive.
    Each request runs in its own asyncio task so the bus message loop
    is never blocked.

    Example::

        @task(name="research")
        async def on_research(self, message):
            ...

    Args:
        name: Task name to match. The handler only receives requests
            with a matching name.
    """

    def decorator(fn: Callable) -> Callable:
        fn.is_task_handler = True  # type: ignore[attr-defined]
        fn.task_name = name  # type: ignore[attr-defined]
        return fn

    return decorator


def _collect_task_handlers(obj) -> dict[str, Callable]:
    seen: set[str] = set()
    handlers: dict[str, Callable] = {}
    for cls in type(obj).__mro__:
        for attr_name, val in cls.__dict__.items():
            if attr_name in seen:
                continue
            seen.add(attr_name)
            if callable(val) and getattr(val, "is_task_handler", False):
                task_name: str = getattr(val, "task_name")
                if task_name in handlers:
                    existing = handlers[task_name].__name__
                    raise ValueError(
                        f"Duplicate @task handler for '{task_name}': "
                        f"'{attr_name}' conflicts with '{existing}'"
                    )
                handlers[task_name] = getattr(obj, attr_name)
    return handlers
