#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""JSON-based bus message serializer with pluggable frame adapters."""

import dataclasses
import json
from typing import Any, Optional

from pipecat.frames.frames import DataFrame, Frame
from pipecat.processors.frame_processor import FrameDirection

from pipecat_subagents.bus.messages import BusFrameMessage, BusMessage

# DataFrame fields that are auto-generated and not meaningful for transport.
_DATAFRAME_FIELDS = {f.name for f in dataclasses.fields(DataFrame)}
from pipecat_subagents.bus.serializers.base import FrameAdapter, MessageSerializer

# Registry of all concrete BusMessage subclasses, built once at import time.
_MESSAGE_TYPES: dict[str, type[BusMessage]] = {}


def _register_message_types() -> None:
    """Walk the BusMessage class hierarchy and register all concrete subclasses."""
    queue = [BusMessage]
    while queue:
        cls = queue.pop()
        _MESSAGE_TYPES[cls.__name__] = cls
        queue.extend(cls.__subclasses__())


_register_message_types()


class JSONMessageSerializer(MessageSerializer):
    """Serialize bus messages as JSON with pluggable frame adapters.

    Frame adapters are registered per frame type. When serializing a
    `BusFrameMessage`, the serializer looks up the adapter for the
    wrapped frame's type and delegates to it. Unregistered frame types
    raise `ValueError`.

    Example::

        serializer = JSONMessageSerializer()
        serializer.register_frame_adapter(TextFrame, TextFrameAdapter())

        data = serializer.serialize(message)
        restored = serializer.deserialize(data)
    """

    def __init__(self):
        """Initialize the JSONMessageSerializer."""
        self._frame_adapters: dict[type[Frame], FrameAdapter] = {}

    def register_frame_adapter(self, frame_type: type[Frame], adapter: FrameAdapter) -> None:
        """Register a frame adapter for a specific frame type.

        Args:
            frame_type: The Pipecat frame class to handle.
            adapter: The adapter that serializes/deserializes this frame type.
        """
        self._frame_adapters[frame_type] = adapter

    def serialize(self, message: BusMessage) -> bytes:
        """Convert a bus message to JSON bytes.

        Args:
            message: The bus message to serialize.

        Returns:
            UTF-8 encoded JSON bytes.

        Raises:
            ValueError: If the message contains a frame with no registered adapter.
        """
        data = self._message_to_dict(message)
        return json.dumps(data, separators=(",", ":")).encode("utf-8")

    def deserialize(self, data: bytes) -> BusMessage:
        """Reconstruct a bus message from JSON bytes.

        Args:
            data: The JSON bytes produced by `serialize()`.

        Returns:
            The reconstructed `BusMessage`.

        Raises:
            ValueError: If the message type is unknown or frame adapter is missing.
        """
        payload = json.loads(data)
        return self._dict_to_message(payload)

    def _message_to_dict(self, message: BusMessage) -> dict[str, Any]:
        """Convert a message to a JSON-compatible dict."""
        type_name = type(message).__name__
        fields: dict[str, Any] = {}

        for f in dataclasses.fields(message):
            if f.name in _DATAFRAME_FIELDS:
                continue
            value = getattr(message, f.name)
            if isinstance(message, BusFrameMessage) and f.name == "frame":
                fields["frame"] = self._serialize_frame(value)
            elif isinstance(value, FrameDirection):
                fields[f.name] = value.name
            elif value is not None:
                fields[f.name] = value

        return {"type": type_name, "fields": fields}

    def _dict_to_message(self, payload: dict[str, Any]) -> BusMessage:
        """Reconstruct a message from a dict."""
        type_name = payload["type"]
        fields = payload["fields"]

        msg_cls = _MESSAGE_TYPES.get(type_name)
        if msg_cls is None:
            raise ValueError(f"Unknown message type: {type_name}")

        if issubclass(msg_cls, BusFrameMessage) and "frame" in fields:
            fields["frame"] = self._deserialize_frame(fields["frame"])

        if "direction" in fields:
            fields["direction"] = FrameDirection[fields["direction"]]

        return msg_cls(**fields)

    def _serialize_frame(self, frame: Frame) -> dict[str, Any]:
        """Serialize a frame using its registered adapter."""
        adapter = self._find_adapter(type(frame))
        if adapter is None:
            raise ValueError(
                f"No frame adapter registered for {type(frame).__name__}. "
                f"Register one with register_frame_adapter()."
            )
        return {
            "type": type(frame).__name__,
            "data": adapter.serialize(frame),
        }

    def _deserialize_frame(self, payload: dict[str, Any]) -> Frame:
        """Deserialize a frame using its registered adapter."""
        frame_type_name = payload["type"]
        # Find the adapter by frame type name
        for frame_type, adapter in self._frame_adapters.items():
            if frame_type.__name__ == frame_type_name:
                return adapter.deserialize(payload["data"])
        raise ValueError(
            f"No frame adapter registered for {frame_type_name}. "
            f"Register one with register_frame_adapter()."
        )

    def _find_adapter(self, frame_type: type[Frame]) -> Optional[FrameAdapter]:
        """Find an adapter for a frame type, checking parent classes."""
        for cls in frame_type.__mro__:
            if cls in self._frame_adapters:
                return self._frame_adapters[cls]
        return None
