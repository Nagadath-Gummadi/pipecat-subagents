#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Bus message serialization for network transport.

Provides the abstract `MessageSerializer` interface, the `TypeAdapter`
base for custom type serialization, and a default `JSONMessageSerializer`
implementation.
"""

from pipecat_subagents.bus.serializers.base import MessageSerializer, TypeAdapter
from pipecat_subagents.bus.serializers.json import JSONMessageSerializer

__all__ = [
    "JSONMessageSerializer",
    "MessageSerializer",
    "TypeAdapter",
]
