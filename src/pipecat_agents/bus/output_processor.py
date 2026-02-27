#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""One-way processor that captures pipeline frames and publishes them to the bus.

Used at the end of LLM agent pipelines to route output frames (text, audio)
back to the session agent via the bus.
"""

from pipecat.frames.frames import CancelFrame, EndFrame, Frame, StartFrame, StopFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from pipecat_agents.bus.bus import AgentBus
from pipecat_agents.bus.messages import BusFrameMessage

_LIFECYCLE_FRAMES = (StartFrame, EndFrame, CancelFrame, StopFrame)


class BusOutputProcessor(FrameProcessor):
    """Captures pipeline frames and publishes them to the bus.

    Placed at the end of an agent's pipeline to wrap non-lifecycle
    frames in `BusFrameMessage` and send them to the bus.
    """

    def __init__(
        self,
        *,
        bus: AgentBus,
        agent_name: str,
        pass_through: bool = False,
        **kwargs,
    ):
        """Initialize the BusOutputProcessor.

        Args:
            bus: The `AgentBus` to publish frames to.
            agent_name: Name of this agent, used as message source.
            pass_through: When True, non-lifecycle frames are both sent
                to the bus **and** passed downstream. Defaults to False.
            **kwargs: Additional arguments passed to `FrameProcessor`.
        """
        super().__init__(**kwargs)
        self._bus = bus
        self._agent_name = agent_name
        self._pass_through = pass_through

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process a frame: pass lifecycle frames through, send others to bus.

        Only intercepts downstream frames. Upstream frames are always
        passed through unchanged.

        Args:
            frame: The frame to process.
            direction: The direction the frame is traveling.
        """
        await super().process_frame(frame, direction)

        # Upstream frames always pass through
        if direction == FrameDirection.UPSTREAM:
            await self.push_frame(frame, direction)
            return

        # Lifecycle frames always pass through, never sent to bus
        if isinstance(frame, _LIFECYCLE_FRAMES):
            await self.push_frame(frame, direction)
            return

        # Send to bus
        msg = BusFrameMessage(
            source=self._agent_name,
            frame=frame,
            direction=direction,
        )
        await self._bus.send(msg)

        # Optionally pass downstream too
        if self._pass_through:
            await self.push_frame(frame, direction)
