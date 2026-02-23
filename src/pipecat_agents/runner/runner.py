#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

"""Agent runner for orchestrating multi-agent lifecycle and pipeline tasks."""

import asyncio
from typing import Optional

from loguru import logger
from pipecat.pipeline.runner import PipelineRunner
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.utils.base_object import BaseObject

from pipecat_agents.agents.base_agent import BaseAgent
from pipecat_agents.bus import (
    AgentActivatedArgs,
    AgentBus,
    BusAddAgentMessage,
    BusAssistantTurnStartedMessage,
    BusAssistantTurnStoppedMessage,
    BusCancelMessage,
    BusClientConnectedMessage,
    BusClientDisconnectedMessage,
    BusEndAgentMessage,
    BusEndMessage,
    BusMessage,
    BusStartAgentMessage,
    BusUserTurnStartedMessage,
    BusUserTurnStoppedMessage,
    LocalAgentBus,
)
from pipecat_agents.runner.user_agent import UserAgent, UserAgentParams


class AgentRunner(BaseObject):
    """Lifecycle orchestrator for multi-agent systems.

    Manages agent lifecycle and coordinates pipeline tasks via
    `PipelineRunner`. The user agent (transport bridge) is created
    internally from `UserAgentParams`; other agents are added via
    `add_agent()`.

    Event handlers:

    on_runner_started(runner)
        Fired after all registered agents have been started.

    on_client_connected(runner, client)
        Fired when a client connects to the transport.

    on_client_disconnected(runner, client)
        Fired when a client disconnects from the transport.

    on_user_turn_started(runner)
        Fired when the user begins speaking.

    on_user_turn_stopped(runner, message)
        Fired when the user stops speaking. The message is a
        `UserTurnStoppedMessage`.

    on_assistant_turn_started(runner)
        Fired when the assistant begins responding.

    on_assistant_turn_stopped(runner, message)
        Fired when the assistant stops responding. The message is an
        `AssistantTurnStoppedMessage`.

    Example::

        runner = AgentRunner(user_agent_params=params)

        @runner.event_handler("on_runner_started")
        async def on_started(runner):
            await runner.activate_agent("greeter")

        @runner.event_handler("on_client_disconnected")
        async def on_disconnected(runner, client):
            await runner.cancel("client left")
    """

    def __init__(
        self,
        *,
        user_agent_params: Optional[UserAgentParams] = None,
        bus: Optional[AgentBus] = None,
        handle_sigint: bool = True,
    ):
        """Initialize the AgentRunner.

        Args:
            user_agent_params: Optional user agent configuration. When
                provided, creates a user agent internally to bridge the
                transport to the bus.
            bus: Optional `AgentBus` instance. Creates a default one if None.
            handle_sigint: Whether `PipelineRunner` handles SIGINT.
                Defaults to True.
        """
        super().__init__()
        self._bus = bus or LocalAgentBus()

        self._running: bool = False
        self._agents: dict[str, BaseAgent] = {}
        self._running_agent_tasks: dict[str, asyncio.Task] = {}
        self._pipecat_runner = PipelineRunner(handle_sigint=handle_sigint)
        self._shutdown_event = asyncio.Event()

        self._user_agent: Optional[UserAgent] = None
        if user_agent_params:
            self._user_agent = UserAgent(bus=self._bus, params=user_agent_params)
            self._agents[self._user_agent.name] = self._user_agent

        self._register_event_handler("on_runner_started")
        self._register_event_handler("on_client_connected")
        self._register_event_handler("on_client_disconnected")
        self._register_event_handler("on_user_turn_started")
        self._register_event_handler("on_user_turn_stopped")
        self._register_event_handler("on_assistant_turn_started")
        self._register_event_handler("on_assistant_turn_stopped")

        @self._bus.event_handler("on_message")
        async def on_message(bus, message: BusMessage):
            await self._handle_bus_message(message)

    @property
    def bus(self) -> AgentBus:
        """The bus instance for agent communication."""
        return self._bus

    @property
    def context_aggregator(self) -> LLMContextAggregatorPair | None:
        """The user agent's context aggregator pair, or None if no context."""
        if self._user_agent:
            return self._user_agent.context_aggregator
        return None

    async def add_agent(self, agent: BaseAgent) -> None:
        """Add an agent to this runner.

        Can be called before or after run(). When called after run() has
        started, the agent's pipeline task is created and started immediately.

        Args:
            agent: The agent to add.

        Raises:
            ValueError: If an agent with this name already exists.
        """
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' already exists")
        self._agents[agent.name] = agent
        logger.debug(f"AgentRunner: added agent '{agent.name}'")

        if self._running:
            await self._start_agent_task(agent)

    async def activate_agent(self, name: str, *, args: Optional[AgentActivatedArgs] = None) -> None:
        """Send a `BusStartAgentMessage` to the named agent.

        Args:
            name: Name of the agent to activate.
            args: Optional `AgentActivatedArgs` forwarded to the agent's
                ``on_agent_activated`` handler.
        """
        await self._bus.send(BusStartAgentMessage(source=self.name, target=name, args=args))

    async def run(self) -> None:
        """Start all agents, block until shutdown.

        Starts all registered agents, fires ``on_runner_started``, then blocks
        until `end()` or `cancel()` is called. New agents can be added
        dynamically via `add_agent()` after ``run()`` has started.
        """
        self._running = True
        self._shutdown_event.clear()

        await self._bus.start()

        for agent in self._agents.values():
            await self._start_agent_task(agent)

        await self._call_event_handler("on_runner_started")

        await self._shutdown_event.wait()

        # Wait for remaining agent tasks to finish cleanup
        remaining = [t for t in self._running_agent_tasks.values() if not t.done()]
        if remaining:
            await asyncio.gather(*remaining, return_exceptions=True)

        await self._bus.stop()
        self._running = False

    async def end(self, reason: Optional[str] = None) -> None:
        """Gracefully end all agent pipelines and shut down.

        Sends `BusEndAgentMessage` to each non-user agent and waits for
        their pipelines to finish. Then ends the user agent so in-flight
        responses (TTS, audio) are fully delivered before shutdown.

        Args:
            reason: Optional human-readable reason for ending.
        """
        logger.info(f"AgentRunner: ending gracefully (reason={reason})")
        await self._end_agents(reason)
        self._shutdown_event.set()

    async def cancel(self, reason: Optional[str] = None) -> None:
        """Cancel the runner and all agent tasks.

        Args:
            reason: Optional human-readable reason for cancelling.
        """
        logger.info(f"AgentRunner: cancelling (reason={reason})")
        await self._bus.send(BusCancelMessage(source=self.name, reason=reason))
        await self._pipecat_runner.cancel()
        self._shutdown_event.set()

    async def _handle_bus_message(self, message: BusMessage) -> None:
        """Handle bus messages directed at the runner."""
        if message.source == self.name:
            return
        if isinstance(message, BusEndMessage):
            asyncio.create_task(self.end(message.reason))
        elif isinstance(message, BusCancelMessage):
            asyncio.create_task(self.cancel(message.reason))
        elif isinstance(message, BusAddAgentMessage) and message.agent:
            await self.add_agent(message.agent)
        elif isinstance(message, BusClientConnectedMessage):
            await self._call_event_handler("on_client_connected", message.client)
        elif isinstance(message, BusClientDisconnectedMessage):
            await self._call_event_handler("on_client_disconnected", message.client)
        elif isinstance(message, BusUserTurnStartedMessage):
            await self._call_event_handler("on_user_turn_started")
        elif isinstance(message, BusUserTurnStoppedMessage):
            await self._call_event_handler("on_user_turn_stopped", message.message)
        elif isinstance(message, BusAssistantTurnStartedMessage):
            await self._call_event_handler("on_assistant_turn_started")
        elif isinstance(message, BusAssistantTurnStoppedMessage):
            await self._call_event_handler("on_assistant_turn_stopped", message.message)

    async def _start_agent_task(self, agent: BaseAgent) -> None:
        """Create an agent's pipeline task and start it as a background asyncio task."""
        pipeline_task = await agent.create_pipeline_task()
        asyncio_task = asyncio.create_task(
            self._pipecat_runner.run(pipeline_task),
            name=f"agent_{agent.name}",
        )
        self._running_agent_tasks[agent.name] = asyncio_task
        asyncio_task.add_done_callback(self._on_agent_task_done)

    def _on_agent_task_done(self, task: asyncio.Task) -> None:
        """Remove a completed agent task from the running tasks dict."""
        name = task.get_name().removeprefix("agent_")
        self._running_agent_tasks.pop(name, None)

    async def _end_agents(self, reason: Optional[str] = None) -> None:
        """End non-user agents first, wait for their pipelines, then end user agent."""
        non_user_tasks = []
        for name, agent in self._agents.items():
            if agent is self._user_agent:
                continue
            await self._bus.send(BusEndAgentMessage(source=self.name, target=name, reason=reason))
            task = self._running_agent_tasks.get(name)
            if task and not task.done():
                non_user_tasks.append(task)

        if non_user_tasks:
            await asyncio.gather(*non_user_tasks, return_exceptions=True)

        if self._user_agent:
            await self._bus.send(
                BusEndAgentMessage(source=self.name, target=self._user_agent.name, reason=reason)
            )
