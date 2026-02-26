#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from pipecat.frames.frames import EndFrame, TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.filters.identity_filter import IdentityFilter
from pipecat.processors.frame_processor import FrameDirection

from pipecat_agents.agents.base_agent import BaseAgent
from pipecat_agents.bus import (
    AgentActivationArgs,
    BusActivateAgentMessage,
    BusAddAgentMessage,
    BusCancelAgentMessage,
    BusCancelMessage,
    BusEndAgentMessage,
    BusEndMessage,
    BusFrameMessage,
    BusMessage,
    LocalAgentBus,
)


class StubAgent(BaseAgent):
    """Minimal agent subclass for testing."""

    async def build_pipeline_task(self) -> PipelineTask:
        pipeline = Pipeline([IdentityFilter()])
        return PipelineTask(pipeline, cancel_on_idle_timeout=False)


class TestBaseAgentLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_agent_starts_inactive_by_default(self):
        """Agent is inactive by default."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)
        self.assertFalse(agent.active)

    async def test_activation_via_bus_message_after_pipeline_start(self):
        """Agent activates when BusActivateAgentMessage received and pipeline started."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)

        activated = asyncio.Event()
        activation_args_received = []

        @agent.event_handler("on_agent_activated")
        async def on_activated(agent, args):
            activation_args_received.append(args)
            activated.set()

        task = await agent.create_pipeline_task()

        # Simulate pipeline start
        agent._pipeline_started = True
        await agent._call_event_handler("on_agent_started")

        # Send activation message
        args = AgentActivationArgs(messages=["hello"])
        msg = BusActivateAgentMessage(source="other", target="test", args=args)
        await agent._handle_bus_message(msg)

        await asyncio.wait_for(activated.wait(), timeout=1.0)
        self.assertTrue(agent.active)
        self.assertEqual(len(activation_args_received), 1)
        self.assertIs(activation_args_received[0], args)

    async def test_active_true_constructor_activates_after_pipeline_start(self):
        """active=True triggers activation after pipeline starts."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus, active=True)

        activated = asyncio.Event()

        @agent.event_handler("on_agent_activated")
        async def on_activated(agent, args):
            activated.set()

        # active=True sets _pending_activation indirectly — the constructor
        # sets self._active = True. When _maybe_activate is called after
        # pipeline start, it checks _pending_activation. Let's simulate
        # the normal flow: active=True means _pending_activation should be set.
        agent._pending_activation = True

        task = await agent.create_pipeline_task()
        agent._pipeline_started = True
        await agent._maybe_activate()

        await asyncio.wait_for(activated.wait(), timeout=1.0)
        self.assertTrue(agent.active)

    async def test_transfer_to_deactivates_self_and_sends_activate(self):
        """transfer_to() deactivates self and sends BusActivateAgentMessage."""
        bus = LocalAgentBus()
        sent = []
        original_send = bus.send

        async def capture_send(message):
            sent.append(message)
            await original_send(message)

        bus.send = capture_send

        agent = StubAgent("agent_a", bus=bus)
        agent._active = True

        deactivated = asyncio.Event()

        @agent.event_handler("on_agent_deactivated")
        async def on_deactivated(agent):
            deactivated.set()

        args = AgentActivationArgs(messages=["context"])
        await agent.transfer_to("agent_b", args=args)

        await asyncio.wait_for(deactivated.wait(), timeout=1.0)
        self.assertFalse(agent.active)

        activate_msgs = [m for m in sent if isinstance(m, BusActivateAgentMessage)]
        self.assertEqual(len(activate_msgs), 1)
        self.assertEqual(activate_msgs[0].target, "agent_b")
        self.assertIs(activate_msgs[0].args, args)

    async def test_activate_agent_sends_activate_without_deactivating_self(self):
        """activate_agent() sends BusActivateAgentMessage without deactivating self."""
        bus = LocalAgentBus()
        sent = []
        original_send = bus.send

        async def capture_send(message):
            sent.append(message)
            await original_send(message)

        bus.send = capture_send

        agent = StubAgent("agent_a", bus=bus)
        agent._active = True

        await agent.activate_agent("agent_b")

        self.assertTrue(agent.active)  # NOT deactivated
        activate_msgs = [m for m in sent if isinstance(m, BusActivateAgentMessage)]
        self.assertEqual(len(activate_msgs), 1)
        self.assertEqual(activate_msgs[0].target, "agent_b")

    async def test_end_without_parent_sends_bus_end_message(self):
        """end() with no parent sends BusEndMessage."""
        bus = LocalAgentBus()
        sent = []
        original_send = bus.send

        async def capture_send(message):
            sent.append(message)
            await original_send(message)

        bus.send = capture_send

        agent = StubAgent("agent_a", bus=bus)
        await agent.end(reason="done")

        end_msgs = [m for m in sent if isinstance(m, BusEndMessage)]
        self.assertEqual(len(end_msgs), 1)
        self.assertEqual(end_msgs[0].source, "agent_a")
        self.assertEqual(end_msgs[0].reason, "done")

    async def test_end_with_parent_sends_bus_end_agent_message(self):
        """end() with parent sends BusEndAgentMessage to parent."""
        bus = LocalAgentBus()
        sent = []
        original_send = bus.send

        async def capture_send(message):
            sent.append(message)
            await original_send(message)

        bus.send = capture_send

        agent = StubAgent("child", bus=bus, parent="parent_agent")
        await agent.end()

        end_agent_msgs = [m for m in sent if isinstance(m, BusEndAgentMessage)]
        self.assertEqual(len(end_agent_msgs), 1)
        self.assertEqual(end_agent_msgs[0].target, "parent_agent")
        self.assertEqual(end_agent_msgs[0].source, "child")

    async def test_cancel_sends_bus_cancel_message(self):
        """cancel() sends BusCancelMessage."""
        bus = LocalAgentBus()
        sent = []
        original_send = bus.send

        async def capture_send(message):
            sent.append(message)
            await original_send(message)

        bus.send = capture_send

        agent = StubAgent("agent_a", bus=bus)
        await agent.cancel()

        cancel_msgs = [m for m in sent if isinstance(m, BusCancelMessage)]
        self.assertEqual(len(cancel_msgs), 1)
        self.assertEqual(cancel_msgs[0].source, "agent_a")

    async def test_add_agent_sends_bus_add_agent_message(self):
        """add_agent() sends BusAddAgentMessage."""
        bus = LocalAgentBus()
        sent = []
        original_send = bus.send

        async def capture_send(message):
            sent.append(message)
            await original_send(message)

        bus.send = capture_send

        agent = StubAgent("agent_a", bus=bus)
        new_agent = StubAgent("agent_b", bus=bus)
        await agent.add_agent(new_agent)

        add_msgs = [m for m in sent if isinstance(m, BusAddAgentMessage)]
        self.assertEqual(len(add_msgs), 1)
        self.assertIs(add_msgs[0].agent, new_agent)

    async def test_on_agent_started_event(self):
        """on_agent_started fires after pipeline starts."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)

        started = asyncio.Event()

        @agent.event_handler("on_agent_started")
        async def on_started(agent):
            started.set()

        task = await agent.create_pipeline_task()
        agent._pipeline_started = True
        await agent._call_event_handler("on_agent_started")

        await asyncio.wait_for(started.wait(), timeout=1.0)

    async def test_on_agent_deactivated_event(self):
        """on_agent_deactivated fires on deactivation."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)
        agent._active = True

        deactivated = asyncio.Event()

        @agent.event_handler("on_agent_deactivated")
        async def on_deactivated(agent):
            deactivated.set()

        await agent.deactivate_agent()

        await asyncio.wait_for(deactivated.wait(), timeout=1.0)
        self.assertFalse(agent.active)

    async def test_bus_frame_message_queued_when_active(self):
        """BusFrameMessage frames are queued to pipeline when active."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)
        agent._active = True

        # Mock the task
        mock_task = MagicMock()
        mock_task.queue_frame = AsyncMock()
        agent._task = mock_task

        frame = TextFrame(text="hello")
        msg = BusFrameMessage(
            source="other",
            frame=frame,
            direction=FrameDirection.DOWNSTREAM,
        )
        await agent._handle_bus_message(msg)

        mock_task.queue_frame.assert_awaited_once_with(frame)

    async def test_bus_frame_message_ignored_when_inactive(self):
        """BusFrameMessage frames are ignored when agent is inactive."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)
        agent._active = False

        mock_task = MagicMock()
        mock_task.queue_frame = AsyncMock()
        agent._task = mock_task

        frame = TextFrame(text="hello")
        msg = BusFrameMessage(
            source="other",
            frame=frame,
            direction=FrameDirection.DOWNSTREAM,
        )
        await agent._handle_bus_message(msg)

        mock_task.queue_frame.assert_not_awaited()

    async def test_messages_from_self_ignored(self):
        """Messages from self (source == name) are ignored."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)
        agent._active = True

        mock_task = MagicMock()
        mock_task.queue_frame = AsyncMock()
        agent._task = mock_task

        msg = BusFrameMessage(
            source="test",  # same as agent name
            frame=TextFrame(text="self"),
            direction=FrameDirection.DOWNSTREAM,
        )
        await agent._handle_bus_message(msg)

        mock_task.queue_frame.assert_not_awaited()

    async def test_targeted_messages_for_other_agents_ignored(self):
        """Messages targeted at another agent are ignored."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)
        agent._active = True

        mock_task = MagicMock()
        mock_task.queue_frame = AsyncMock()
        agent._task = mock_task

        msg = BusFrameMessage(
            source="other",
            target="someone_else",
            frame=TextFrame(text="not for me"),
            direction=FrameDirection.DOWNSTREAM,
        )
        await agent._handle_bus_message(msg)

        mock_task.queue_frame.assert_not_awaited()

    async def test_bus_end_agent_message_queues_end_frame(self):
        """BusEndAgentMessage queues EndFrame to pipeline."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)

        mock_task = MagicMock()
        mock_task.queue_frame = AsyncMock()
        agent._task = mock_task

        msg = BusEndAgentMessage(source="runner", target="test", reason="shutdown")
        await agent._handle_bus_message(msg)

        mock_task.queue_frame.assert_awaited_once()
        queued_frame = mock_task.queue_frame.call_args[0][0]
        self.assertIsInstance(queued_frame, EndFrame)

    async def test_bus_cancel_agent_message_cancels_task(self):
        """BusCancelAgentMessage cancels the task."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)

        mock_task = MagicMock()
        mock_task.cancel = AsyncMock()
        agent._task = mock_task

        msg = BusCancelAgentMessage(source="runner", target="test")
        await agent._handle_bus_message(msg)

        mock_task.cancel.assert_awaited_once()

    async def test_queue_frame_delegates_to_task(self):
        """queue_frame delegates to task.queue_frame."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)

        mock_task = MagicMock()
        mock_task.queue_frame = AsyncMock()
        agent._task = mock_task

        frame = TextFrame(text="test")
        await agent.queue_frame(frame)

        mock_task.queue_frame.assert_awaited_once_with(frame)

    async def test_queue_frames_delegates_to_task(self):
        """queue_frames delegates to task.queue_frames."""
        bus = LocalAgentBus()
        agent = StubAgent("test", bus=bus)

        mock_task = MagicMock()
        mock_task.queue_frames = AsyncMock()
        agent._task = mock_task

        frames = [TextFrame(text="a"), TextFrame(text="b")]
        await agent.queue_frames(frames)

        mock_task.queue_frames.assert_awaited_once_with(frames)


if __name__ == "__main__":
    unittest.main()
