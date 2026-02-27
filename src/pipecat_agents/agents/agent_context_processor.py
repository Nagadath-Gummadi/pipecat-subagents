#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Processor that wraps a shared context with agent-specific system messages.

Used at the front of an ``LLMContextAgent`` pipeline to prepend the agent's
system messages to the shared conversation context before forwarding to the LLM.
"""

from typing import List

from pipecat.frames.frames import Frame, LLMContextFrame, LLMMessagesAppendFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor


class AgentContextProcessor(FrameProcessor):
    """Prepends agent system messages to shared context frames.

    On ``LLMContextFrame``: creates a new ``LLMContext`` containing the
    agent's system messages followed by the shared context messages, then
    pushes a new ``LLMContextFrame`` with the combined context.

    On ``LLMMessagesAppendFrame``: appends the messages to the agent's
    context and, if ``run_llm`` is set, pushes an ``LLMContextFrame``
    with the updated agent context.

    All other frames pass through unchanged.
    """

    def __init__(self, *, system_messages: List[dict], **kwargs):
        """Initialize the AgentContextProcessor.

        Args:
            system_messages: List of message dicts (e.g.
                ``[{"role": "system", "content": "..."}]``) to prepend
                to every shared context.
            **kwargs: Additional arguments passed to ``FrameProcessor``.
        """
        super().__init__(**kwargs)
        self._system_messages = list(system_messages)
        self._context = LLMContext(list(system_messages))

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process a frame, wrapping context frames with system messages.

        Only intercepts downstream frames. Upstream frames pass through
        unchanged.

        Args:
            frame: The frame to process.
            direction: The direction the frame is traveling.
        """
        await super().process_frame(frame, direction)

        if direction == FrameDirection.UPSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, LLMContextFrame):
            shared_messages = frame.context.get_messages()
            agent_messages = list(self._system_messages) + list(shared_messages)
            self._context.set_messages(agent_messages)
            await self.push_frame(LLMContextFrame(context=self._context))
        elif isinstance(frame, LLMMessagesAppendFrame):
            self._context.add_messages(frame.messages)
            if frame.run_llm:
                await self.push_frame(LLMContextFrame(context=self._context))
        else:
            await self.push_frame(frame, direction)
