#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Abstract agent bus for inter-agent pub/sub messaging.

Provides the abstract `AgentBus` base class. Concrete implementations
(e.g. `LocalAgentBus`) live in separate modules.
"""

import asyncio
from abc import abstractmethod

from pipecat.utils.base_object import BaseObject

from pipecat_agents.bus.messages import BusMessage
from pipecat_agents.bus.subscriber import BusSubscriber


class AgentBus(BaseObject):
    """Abstract base for inter-agent and runner-agent communication.

    Subclasses implement `send()` and `receive()`. The base class runs a
    background receive loop that dispatches incoming messages to all
    subscribers.

    Subscribers are registered via `subscribe()`. Each subscriber gets
    its own queue and task so that slow handlers never block other
    subscribers.
    """

    def __init__(self, **kwargs):
        """Initialize the AgentBus.

        Args:
            **kwargs: Additional arguments passed to `BaseObject`.
        """
        super().__init__(**kwargs)
        self._receive_task: asyncio.Task | None = None
        self._subscribers: list[tuple[BusSubscriber, asyncio.Queue]] = []
        self._subscriber_tasks: list[asyncio.Task] = []
        self._running = False

    def subscribe(self, subscriber: BusSubscriber) -> None:
        """Register a subscriber to receive bus messages.

        Each subscriber gets a dedicated queue. If the bus is already
        running, a delivery task is started immediately.

        Args:
            subscriber: The `BusSubscriber` to register.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append((subscriber, queue))
        if self._running:
            task = asyncio.create_task(self._subscriber_task(subscriber, queue))
            self._subscriber_tasks.append(task)

    def unsubscribe(self, subscriber: BusSubscriber) -> None:
        """Remove a subscriber and cancel its delivery task.

        Args:
            subscriber: The `BusSubscriber` to remove.
        """
        for i, (sub, _queue) in enumerate(self._subscribers):
            if sub is subscriber:
                if i < len(self._subscriber_tasks):
                    self._subscriber_tasks[i].cancel()
                    self._subscriber_tasks.pop(i)
                self._subscribers.pop(i)
                return

    async def start(self):
        """Start the background receive loop and all subscriber tasks."""
        self._running = True
        self._subscriber_tasks = [
            asyncio.create_task(self._subscriber_task(sub, queue))
            for sub, queue in self._subscribers
        ]
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def stop(self):
        """Stop the background receive loop and all subscriber tasks."""
        self._running = False
        for task in self._subscriber_tasks:
            task.cancel()
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        for task in self._subscriber_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._subscriber_tasks.clear()

    @abstractmethod
    async def send(self, message: BusMessage) -> None:
        """Send a message through the bus.

        Args:
            message: The bus message to send.
        """
        pass

    @abstractmethod
    async def receive(self) -> BusMessage:
        """Wait for and return the next message from the bus."""
        pass

    async def _receive_loop(self):
        """Pull messages from `receive()` and dispatch to subscribers."""
        while True:
            message = await self.receive()
            # Fan out to subscriber queues
            for _sub, queue in self._subscribers:
                queue.put_nowait(message)

    async def _subscriber_task(self, subscriber: BusSubscriber, queue: asyncio.Queue):
        """Deliver messages from *queue* to *subscriber*."""
        try:
            while True:
                message = await queue.get()
                await subscriber.on_bus_message(message)
        except asyncio.CancelledError:
            pass
