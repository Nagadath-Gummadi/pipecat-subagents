#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Bus message serialization for network transport.

Provides the abstract `MessageSerializer` interface and a default
`JSONMessageSerializer` implementation with pluggable frame adapters.
"""

from pipecat_subagents.bus.serializers.base import FrameAdapter, MessageSerializer
from pipecat_subagents.bus.serializers.json import JSONMessageSerializer

__all__ = [
    "FrameAdapter",
    "JSONMessageSerializer",
    "MessageSerializer",
]
