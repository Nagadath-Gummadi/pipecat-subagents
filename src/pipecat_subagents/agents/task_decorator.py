#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Decorator for marking agent methods as task handlers."""


def task(fn=None, *, name: str | None = None):
    """Mark an agent method as a task handler.

    Decorated methods are automatically collected by ``BaseAgent`` at
    initialization and dispatched when matching task requests arrive.
    Each request runs in its own asyncio task so the bus message loop
    is never blocked.

    Can be used with or without arguments::

        @task
        async def on_task_request(self, message):
            ...

        @task(name="research")
        async def on_research(self, message):
            ...

    Args:
        fn: The function to decorate (when used without arguments).
        name: Optional task name to match. When set, this handler only
            receives requests with a matching name. When None, handles
            all unnamed requests (or requests with no matching named
            handler).
    """

    def decorator(fn):
        fn.is_task_handler = True
        fn.task_name = name
        return fn

    if fn is not None:
        return decorator(fn)
    return decorator


def _collect_task_handlers(obj) -> dict:
    """Collect all ``@task`` decorated bound methods from an object.

    Returns a dict mapping task name (or None for the default handler)
    to the bound method.

    Raises:
        ValueError: If two handlers share the same task name.
    """
    seen: set[str] = set()
    handlers: dict[str | None, object] = {}
    for cls in type(obj).__mro__:
        for attr_name, val in cls.__dict__.items():
            if attr_name in seen:
                continue
            seen.add(attr_name)
            if callable(val) and getattr(val, "is_task_handler", False):
                task_name = val.task_name
                if task_name in handlers:
                    existing = handlers[task_name].__name__
                    label = f"'{task_name}'" if task_name else "default (unnamed)"
                    raise ValueError(
                        f"Duplicate @task handler for {label}: "
                        f"'{attr_name}' conflicts with '{existing}'"
                    )
                handlers[task_name] = getattr(obj, attr_name)
    return handlers
