#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Abstract base classes for bus message serialization."""

from abc import ABC, abstractmethod
from typing import Any

from pipecat.frames.frames import Frame

from pipecat_subagents.bus.messages import BusMessage


class FrameAdapter(ABC):
    """Serialize and deserialize a specific Pipecat frame type.

    Each adapter handles one or more frame types, converting them to/from
    a JSON-compatible dict representation suitable for network transport.
    """

    @abstractmethod
    def serialize(self, frame: Frame) -> dict[str, Any]:
        """Convert a frame to a JSON-compatible dict.

        Args:
            frame: The Pipecat frame to serialize.

        Returns:
            A dict representation of the frame.
        """
        pass

    @abstractmethod
    def deserialize(self, data: dict[str, Any]) -> Frame:
        """Reconstruct a frame from a dict.

        Args:
            data: The dict representation produced by `serialize()`.

        Returns:
            The reconstructed Pipecat frame.
        """
        pass


class MessageSerializer(ABC):
    """Serialize and deserialize `BusMessage` instances for network transport.

    Network bus implementations use a `MessageSerializer` to convert messages
    to bytes for transmission and reconstruct them on the receiving end.
    """

    @abstractmethod
    def serialize(self, message: BusMessage) -> bytes:
        """Convert a bus message to bytes.

        Args:
            message: The bus message to serialize.

        Returns:
            The serialized bytes.
        """
        pass

    @abstractmethod
    def deserialize(self, data: bytes) -> BusMessage:
        """Reconstruct a bus message from bytes.

        Args:
            data: The serialized bytes produced by `serialize()`.

        Returns:
            The reconstructed `BusMessage`.
        """
        pass
