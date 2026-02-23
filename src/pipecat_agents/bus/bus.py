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


class AgentBus(BaseObject):
    """Abstract base for inter-agent and runner-agent communication.

    Subclasses implement `send()` and `receive()`. The base class runs a
    background receive loop that dispatches incoming messages to all
    `on_message` subscribers in order.

    Events:
        on_message(bus, message: BusMessage): Fired for every message
            received by the bus. Subscribers filter by source/target.

    Example::

        @bus.event_handler("on_message")
        async def on_message(bus, message: BusMessage):
            if message.target == self._name:
                await self._handle(message)
    """

    def __init__(self, **kwargs):
        """Initialize the AgentBus.

        Args:
            **kwargs: Additional arguments passed to `BaseObject`.
        """
        super().__init__(**kwargs)
        self._register_event_handler("on_message", sync=True)
        self._receive_task: asyncio.Task | None = None

    async def start(self):
        """Start the background receive loop."""
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def stop(self):
        """Stop the background receive loop."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

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
            await self._call_event_handler("on_message", message)
