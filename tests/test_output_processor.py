#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import asyncio
import unittest

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    StartFrame,
    StopFrame,
    TextFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.tests.utils import run_test

from pipecat_agents.bus import BusFrameMessage, BusOutputProcessor, LocalAgentBus


class TestBusOutputProcessor(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_frames_pass_through(self):
        """StartFrame, EndFrame, CancelFrame, StopFrame pass downstream, never sent to bus."""
        bus = LocalAgentBus()
        sent_to_bus = []
        original_send = bus.send

        async def capture_send(msg):
            sent_to_bus.append(msg)
            await original_send(msg)

        bus.send = capture_send

        processor = BusOutputProcessor(bus=bus, agent_name="test_agent")
        pipeline = Pipeline([processor])

        # Send a TextFrame, then EndFrame to terminate
        frames_to_send = [TextFrame(text="hello")]
        # StartFrame and EndFrame pass through; TextFrame goes to bus instead
        expected_down_frames = []
        await run_test(
            pipeline,
            frames_to_send=frames_to_send,
            expected_down_frames=expected_down_frames,
        )

        # Only the TextFrame should be on the bus
        bus_frame_msgs = [m for m in sent_to_bus if isinstance(m, BusFrameMessage)]
        self.assertEqual(len(bus_frame_msgs), 1)
        self.assertIsInstance(bus_frame_msgs[0].frame, TextFrame)

    async def test_non_lifecycle_frames_sent_to_bus(self):
        """Non-lifecycle frames are wrapped in BusFrameMessage and sent to bus."""
        bus = LocalAgentBus()
        sent_to_bus = []
        original_send = bus.send

        async def capture_send(msg):
            sent_to_bus.append(msg)
            await original_send(msg)

        bus.send = capture_send

        processor = BusOutputProcessor(bus=bus, agent_name="test_agent")
        pipeline = Pipeline([processor])

        frames_to_send = [TextFrame(text="hello")]
        await run_test(pipeline, frames_to_send=frames_to_send, expected_down_frames=[])

        bus_frame_msgs = [m for m in sent_to_bus if isinstance(m, BusFrameMessage)]
        self.assertEqual(len(bus_frame_msgs), 1)
        msg = bus_frame_msgs[0]
        self.assertIsInstance(msg.frame, TextFrame)
        self.assertEqual(msg.frame.text, "hello")
        self.assertEqual(msg.direction, FrameDirection.DOWNSTREAM)

    async def test_message_source_is_agent_name(self):
        """BusFrameMessage.source is set to the agent name."""
        bus = LocalAgentBus()
        sent_to_bus = []
        original_send = bus.send

        async def capture_send(msg):
            sent_to_bus.append(msg)
            await original_send(msg)

        bus.send = capture_send

        processor = BusOutputProcessor(bus=bus, agent_name="my_agent")
        pipeline = Pipeline([processor])

        frames_to_send = [TextFrame(text="test")]
        await run_test(pipeline, frames_to_send=frames_to_send, expected_down_frames=[])

        bus_frame_msgs = [m for m in sent_to_bus if isinstance(m, BusFrameMessage)]
        self.assertEqual(len(bus_frame_msgs), 1)
        self.assertEqual(bus_frame_msgs[0].source, "my_agent")


if __name__ == "__main__":
    unittest.main()
