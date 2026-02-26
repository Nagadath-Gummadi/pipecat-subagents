#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import asyncio
import unittest

from pipecat.frames.frames import (
    EndFrame,
    Frame,
    StartFrame,
    TextFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.tests.utils import run_test

from pipecat_agents.bus import (
    BusBridgeProcessor,
    BusFrameMessage,
    LocalAgentBus,
)


class TestBusBridgeProcessor(unittest.IsolatedAsyncioTestCase):
    async def test_lifecycle_frames_pass_through(self):
        """Lifecycle frames pass through and are not sent to the bus."""
        bus = LocalAgentBus()
        sent_to_bus = []
        original_send = bus.send

        async def capture_send(msg):
            sent_to_bus.append(msg)
            await original_send(msg)

        bus.send = capture_send

        processor = BusBridgeProcessor(bus=bus, agent_name="bridge_agent")
        pipeline = Pipeline([processor])

        # TextFrame should be sent to bus (consumed), not pass through
        frames_to_send = [TextFrame(text="hello")]
        expected_down_frames = []
        await run_test(
            pipeline,
            frames_to_send=frames_to_send,
            expected_down_frames=expected_down_frames,
        )

        # Only the TextFrame should have been sent to bus
        bus_msgs = [m for m in sent_to_bus if isinstance(m, BusFrameMessage)]
        self.assertEqual(len(bus_msgs), 1)
        self.assertIsInstance(bus_msgs[0].frame, TextFrame)

    async def test_non_lifecycle_frames_consumed(self):
        """Non-lifecycle downstream frames are sent to bus and not passed through."""
        bus = LocalAgentBus()
        sent_to_bus = []
        original_send = bus.send

        async def capture_send(msg):
            sent_to_bus.append(msg)
            await original_send(msg)

        bus.send = capture_send

        processor = BusBridgeProcessor(bus=bus, agent_name="bridge_agent")
        pipeline = Pipeline([processor])

        frames_to_send = [TextFrame(text="consumed")]
        # No frames pass through downstream (consumed by bridge)
        expected_down_frames = []
        await run_test(
            pipeline,
            frames_to_send=frames_to_send,
            expected_down_frames=expected_down_frames,
        )

        bus_msgs = [m for m in sent_to_bus if isinstance(m, BusFrameMessage)]
        self.assertEqual(len(bus_msgs), 1)
        self.assertEqual(bus_msgs[0].source, "bridge_agent")

    async def test_frames_from_bus_pushed_downstream(self):
        """Frames received from bus are pushed downstream in the pipeline."""
        bus = LocalAgentBus()
        processor = BusBridgeProcessor(bus=bus, agent_name="bridge_agent")

        downstream_frames = []

        class CaptureSink(FrameProcessor):
            async def process_frame(self, frame: Frame, direction: FrameDirection):
                await super().process_frame(frame, direction)
                if isinstance(frame, TextFrame):
                    downstream_frames.append(frame)
                await self.push_frame(frame, direction)

        pipeline = Pipeline([processor, CaptureSink()])
        task = PipelineTask(pipeline, cancel_on_idle_timeout=False)

        async def send_bus_frame():
            await asyncio.sleep(0.05)
            frame = TextFrame(text="from_bus")
            msg = BusFrameMessage(
                source="other_agent",
                frame=frame,
                direction=FrameDirection.DOWNSTREAM,
            )
            await bus._call_event_handler("on_message", msg)
            await asyncio.sleep(0.05)
            await task.queue_frame(EndFrame())

        runner = PipelineRunner()
        await asyncio.gather(
            runner.run(task),
            send_bus_frame(),
        )

        self.assertEqual(len(downstream_frames), 1)
        self.assertEqual(downstream_frames[0].text, "from_bus")

    async def test_frames_buffered_before_start(self):
        """Frames received before StartFrame are buffered and flushed after start."""
        bus = LocalAgentBus()
        processor = BusBridgeProcessor(bus=bus, agent_name="bridge_agent")

        # Simulate a frame arriving before the pipeline starts
        frame = TextFrame(text="early_frame")
        msg = BusFrameMessage(
            source="other_agent",
            frame=frame,
            direction=FrameDirection.DOWNSTREAM,
        )
        # Dispatch directly to the handler — pipeline hasn't started yet
        await bus._call_event_handler("on_message", msg)

        # The frame should be buffered
        self.assertEqual(len(processor._pending_frames), 1)
        self.assertIs(processor._pending_frames[0][0], frame)

    async def test_messages_from_self_ignored(self):
        """BusFrameMessage from the same agent name is ignored."""
        bus = LocalAgentBus()
        processor = BusBridgeProcessor(bus=bus, agent_name="bridge_agent")

        # Simulate a message from self
        frame = TextFrame(text="self_msg")
        msg = BusFrameMessage(
            source="bridge_agent",  # same as processor agent_name
            frame=frame,
            direction=FrameDirection.DOWNSTREAM,
        )
        await bus._call_event_handler("on_message", msg)

        # Should not be buffered
        self.assertEqual(len(processor._pending_frames), 0)

    async def test_targeted_messages_for_other_agents_ignored(self):
        """BusFrameMessage targeted at another agent is ignored."""
        bus = LocalAgentBus()
        processor = BusBridgeProcessor(bus=bus, agent_name="bridge_agent")

        frame = TextFrame(text="not_for_me")
        msg = BusFrameMessage(
            source="other_agent",
            target="someone_else",  # not bridge_agent
            frame=frame,
            direction=FrameDirection.DOWNSTREAM,
        )
        await bus._call_event_handler("on_message", msg)

        self.assertEqual(len(processor._pending_frames), 0)


if __name__ == "__main__":
    unittest.main()
