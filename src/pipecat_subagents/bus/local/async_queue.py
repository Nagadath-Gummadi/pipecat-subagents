#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""In-process agent bus backed by asyncio queues."""

from loguru import logger

from pipecat_subagents.bus.bus import AgentBus
from pipecat_subagents.bus.messages import BusMessage


class AsyncQueueBus(AgentBus):
    """In-process bus that delivers messages via priority queues."""

    async def send(self, message: BusMessage) -> None:
        """Fan out a message to all subscriber priority queues.

        Args:
            message: The bus message to send.
        """
        logger.trace(f"{self}: sending {message}")
        self.on_message_received(message)
