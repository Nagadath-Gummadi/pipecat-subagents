#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""In-process agent bus backed by an asyncio queue."""

import asyncio

from pipecat_agents.bus.bus import AgentBus
from pipecat_agents.bus.messages import BusMessage


class LocalAgentBus(AgentBus):
    """In-process bus backed by an `asyncio.Queue`.

    `send()` enqueues without blocking; the base-class receive loop
    dispatches messages to subscribers in order.
    """

    def __init__(self, **kwargs):
        """Initialize the LocalAgentBus.

        Args:
            **kwargs: Additional arguments passed to `AgentBus`.
        """
        super().__init__(**kwargs)
        self._queue: asyncio.Queue[BusMessage] = asyncio.Queue()

    async def send(self, message: BusMessage) -> None:
        """Enqueue a message for delivery by the receive loop.

        Args:
            message: The bus message to send.
        """
        await self._queue.put(message)

    async def receive(self) -> BusMessage:
        """Wait for and return the next message from the queue.

        Returns:
            The next `BusMessage` in the queue.
        """
        return await self._queue.get()
