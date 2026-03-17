#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import unittest
from typing import Any

from pipecat.frames.frames import Frame, TextFrame
from pipecat.processors.frame_processor import FrameDirection

from pipecat_subagents.bus.messages import (
    BusActivateAgentMessage,
    BusCancelMessage,
    BusEndMessage,
    BusFrameMessage,
    BusMessage,
    BusTaskRequestMessage,
    BusTaskResponseMessage,
)
from pipecat_subagents.bus.serializers import (
    FrameAdapter,
    JSONMessageSerializer,
)


class TextFrameAdapter(FrameAdapter):
    """Test adapter for TextFrame."""

    def serialize(self, frame: Frame) -> dict[str, Any]:
        return {"text": frame.text}

    def deserialize(self, data: dict[str, Any]) -> Frame:
        return TextFrame(text=data["text"])


class TestJSONMessageSerializer(unittest.TestCase):
    def setUp(self):
        self.serializer = JSONMessageSerializer()
        self.serializer.register_frame_adapter(TextFrame, TextFrameAdapter())

    def test_round_trip_simple_message(self):
        """BusMessage serializes and deserializes correctly."""
        msg = BusMessage(source="agent_a", target="agent_b")
        data = self.serializer.serialize(msg)
        restored = self.serializer.deserialize(data)

        self.assertIsInstance(restored, BusMessage)
        self.assertEqual(restored.source, "agent_a")
        self.assertEqual(restored.target, "agent_b")

    def test_round_trip_broadcast_message(self):
        """Broadcast message (no target) round-trips."""
        msg = BusMessage(source="agent_a")
        data = self.serializer.serialize(msg)
        restored = self.serializer.deserialize(data)

        self.assertIsInstance(restored, BusMessage)
        self.assertEqual(restored.source, "agent_a")
        self.assertIsNone(restored.target)

    def test_round_trip_activate_message(self):
        """BusActivateAgentMessage with args round-trips."""
        msg = BusActivateAgentMessage(
            source="parent",
            target="child",
            args={"messages": [{"role": "user", "content": "hello"}]},
        )
        data = self.serializer.serialize(msg)
        restored = self.serializer.deserialize(data)

        self.assertIsInstance(restored, BusActivateAgentMessage)
        self.assertEqual(restored.source, "parent")
        self.assertEqual(restored.target, "child")
        self.assertEqual(restored.args["messages"][0]["content"], "hello")

    def test_round_trip_end_message(self):
        """BusEndMessage round-trips."""
        msg = BusEndMessage(source="agent_a", reason="done")
        data = self.serializer.serialize(msg)
        restored = self.serializer.deserialize(data)

        self.assertIsInstance(restored, BusEndMessage)
        self.assertEqual(restored.reason, "done")

    def test_round_trip_cancel_message(self):
        """BusCancelMessage round-trips."""
        msg = BusCancelMessage(source="agent_a", reason="abort")
        data = self.serializer.serialize(msg)
        restored = self.serializer.deserialize(data)

        self.assertIsInstance(restored, BusCancelMessage)
        self.assertEqual(restored.reason, "abort")

    def test_round_trip_task_request(self):
        """BusTaskRequestMessage with payload round-trips."""
        msg = BusTaskRequestMessage(
            source="parent",
            target="worker",
            task_id="t-123",
            payload={"key": "value"},
        )
        data = self.serializer.serialize(msg)
        restored = self.serializer.deserialize(data)

        self.assertIsInstance(restored, BusTaskRequestMessage)
        self.assertEqual(restored.task_id, "t-123")
        self.assertEqual(restored.payload, {"key": "value"})

    def test_round_trip_task_response(self):
        """BusTaskResponseMessage round-trips."""
        msg = BusTaskResponseMessage(
            source="worker",
            target="parent",
            task_id="t-123",
            response={"result": 42},
        )
        data = self.serializer.serialize(msg)
        restored = self.serializer.deserialize(data)

        self.assertIsInstance(restored, BusTaskResponseMessage)
        self.assertEqual(restored.task_id, "t-123")
        self.assertEqual(restored.response, {"result": 42})
        self.assertEqual(restored.status, "completed")

    def test_round_trip_frame_message(self):
        """BusFrameMessage with TextFrame round-trips via adapter."""
        msg = BusFrameMessage(
            source="agent_a",
            frame=TextFrame(text="hello world"),
            direction=FrameDirection.DOWNSTREAM,
        )
        data = self.serializer.serialize(msg)
        restored = self.serializer.deserialize(data)

        self.assertIsInstance(restored, BusFrameMessage)
        self.assertIsInstance(restored.frame, TextFrame)
        self.assertEqual(restored.frame.text, "hello world")
        self.assertEqual(restored.direction, FrameDirection.DOWNSTREAM)
        self.assertEqual(restored.source, "agent_a")

    def test_frame_message_upstream_direction(self):
        """UPSTREAM direction preserved in round-trip."""
        msg = BusFrameMessage(
            source="agent_a",
            frame=TextFrame(text="up"),
            direction=FrameDirection.UPSTREAM,
        )
        data = self.serializer.serialize(msg)
        restored = self.serializer.deserialize(data)

        self.assertEqual(restored.direction, FrameDirection.UPSTREAM)

    def test_unregistered_frame_raises(self):
        """Serializing a frame with no adapter raises ValueError."""
        serializer = JSONMessageSerializer()  # no adapters registered

        msg = BusFrameMessage(
            source="agent_a",
            frame=TextFrame(text="hello"),
            direction=FrameDirection.DOWNSTREAM,
        )
        with self.assertRaises(ValueError) as ctx:
            serializer.serialize(msg)
        self.assertIn("TextFrame", str(ctx.exception))

    def test_unknown_message_type_raises(self):
        """Deserializing an unknown message type raises ValueError."""
        bad_data = b'{"type":"BogusMessage","fields":{"source":"a"}}'
        with self.assertRaises(ValueError) as ctx:
            self.serializer.deserialize(bad_data)
        self.assertIn("BogusMessage", str(ctx.exception))

    def test_serialized_is_bytes(self):
        """serialize() returns bytes."""
        msg = BusMessage(source="a")
        data = self.serializer.serialize(msg)
        self.assertIsInstance(data, bytes)

    def test_adapter_mro_lookup(self):
        """Adapter registered for a parent class handles subclasses."""

        class CustomTextFrame(TextFrame):
            pass

        msg = BusFrameMessage(
            source="a",
            frame=CustomTextFrame(text="sub"),
            direction=FrameDirection.DOWNSTREAM,
        )
        # TextFrameAdapter is registered for TextFrame, should handle subclass
        data = self.serializer.serialize(msg)
        self.assertIsInstance(data, bytes)


if __name__ == "__main__":
    unittest.main()
