#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""In-process agent bus backed by asyncio queues."""

from loguru import logger

from pipecat_subagents.bus.bus import AgentBus
from pipecat_subagents.bus.messages import BusMessage
from pipecat_subagents.bus.queue import BusMessageQueue


class AsyncQueueBus(AgentBus):
    """In-process bus that delivers messages via per-subscriber priority queues."""

    def __init__(self, **kwargs):
        """Initialize the AsyncQueueBus.

        Args:
            **kwargs: Additional arguments passed to `AgentBus`.
        """
        super().__init__(**kwargs)
        self._queues: list[BusMessageQueue] = []

    async def connect(self) -> BusMessageQueue:
        """Create a per-subscriber priority queue.

        Returns:
            A `BusMessageQueue` that `receive()` reads from.
        """
        queue = BusMessageQueue()
        self._queues.append(queue)
        return queue

    async def disconnect(self, client: BusMessageQueue) -> None:
        """Remove a subscriber's queue from the fan-out list.

        Args:
            client: The queue returned by `connect()`.
        """
        try:
            self._queues.remove(client)
        except ValueError:
            pass

    async def send(self, message: BusMessage) -> None:
        """Fan out a message to all subscriber queues.

        Args:
            message: The bus message to send.
        """
        logger.trace(f"{self}: sending {message}")
        for queue in self._queues:
            queue.put_nowait(message)

    async def receive(self, client: BusMessageQueue) -> BusMessage:
        """Wait for and return the next message from a subscriber queue.

        Args:
            client: The queue returned by `connect()`.

        Returns:
            The next `BusMessage` in the queue.
        """
        message = await client.get()
        logger.trace(f"{self}: received {message}")
        return message
