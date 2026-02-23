#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""LLM agent base class with startup behavior and tool registration.

Provides the `LLMAgent` class that extends `BaseAgent` with an LLM pipeline
and automatic tool registration.
"""

from abc import abstractmethod
from typing import List, Optional

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import LLMMessagesAppendFrame, LLMSetToolsFrame
from pipecat.pipeline.task import PipelineParams
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.llm_service import LLMService

from pipecat_agents.agents.base_agent import BaseAgent
from pipecat_agents.bus import AgentBus
from pipecat_agents.bus.messages import AgentActivatedArgs


class LLMAgent(BaseAgent):
    """Base class for agents with an LLM pipeline.

    Pipeline: ``LLM → BusOutput``

    On activation, sets tools (via `build_tools()`) and appends any
    messages passed via `activate_agent()` or `transfer_to()` to the
    LLM context.

    Turn detection and context aggregation live in the `UserAgent`.

    Event handlers:

    on_agent_activated(agent, args)
        Sets the agent's tools via `build_tools()` and appends any
        activation messages to the LLM context.

    Example::

        agent = MyLLMAgent(name="my_agent", bus=bus)

        @agent.event_handler("on_agent_activated")
        async def on_activated(agent, args: Optional[AgentActivatedArgs]):
            logger.info(f"Agent {agent} activated with args: {args}")
    """

    def __init__(
        self,
        name: str,
        *,
        bus: AgentBus,
        active: bool = False,
        pipeline_params: Optional[PipelineParams] = None,
    ):
        """Initialize the LLMAgent.

        Args:
            name: Unique name for this agent.
            bus: The `AgentBus` for inter-agent communication.
            active: Whether the agent starts active. Defaults to False.
            pipeline_params: Optional `PipelineParams` for this agent's task.
        """
        super().__init__(name, bus=bus, active=active, pipeline_params=pipeline_params)

        @self.event_handler("on_agent_activated")
        async def on_agent_activated(agent, args: Optional[AgentActivatedArgs]):
            tools = self.build_tools()
            if tools:
                await self.queue_frame(LLMSetToolsFrame(tools=ToolsSchema(standard_tools=tools)))

            if args and args.messages:
                await self.queue_frame(LLMMessagesAppendFrame(messages=args.messages, run_llm=True))

    def build_tools(self) -> List[FunctionSchema]:
        """Return the function schemas for this agent's LLM tools.

        Override in subclasses to register tools. Called on each agent
        start via the on_agent_activated handler. Default returns an empty list.

        Returns:
            List of `FunctionSchema` objects to register with the LLM.
        """
        return []

    @abstractmethod
    def build_llm(self) -> LLMService:
        """Return the LLM service for this agent's pipeline.

        Returns:
            An `LLMService` instance used as the sole pipeline processor.
        """
        pass

    def build_pipeline_processors(self) -> List[FrameProcessor]:
        """Return the LLM service as the sole pipeline processor.

        Returns:
            Single-element list containing the `LLMService` from `build_llm()`.
        """
        return [self.build_llm()]
