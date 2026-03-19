#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Agent base classes for the multi-agent framework.

This package provides the core agent hierarchy:

- `BaseAgent`: Abstract base with bus integration and lifecycle management.
- `DetachedAgent`: Agent with a pipeline detached from transport, connected
  via bus frame routing and handoff semantics.
- `LLMDetachedAgent`: Agent with an LLM pipeline (BusInput -> LLM -> BusOutput).
- `FlowsDetachedAgent`: Agent that uses Pipecat Flows for structured conversation.
"""

from pipecat_subagents.agents.base_agent import ActivationArgs, BaseAgent
from pipecat_subagents.agents.detached_agent import DetachedAgent
from pipecat_subagents.agents.flows_detached_agent import FlowsDetachedAgent
from pipecat_subagents.agents.llm_detached_agent import LLMActivationArgs, LLMDetachedAgent
from pipecat_subagents.agents.tool import tool

__all__ = [
    "ActivationArgs",
    "BaseAgent",
    "DetachedAgent",
    "FlowsDetachedAgent",
    "LLMActivationArgs",
    "LLMDetachedAgent",
    "tool",
]
