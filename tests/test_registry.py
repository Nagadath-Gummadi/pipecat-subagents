#
# Copyright (c) 2026, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import unittest

from pipecat_subagents.registry import AgentRegistry
from pipecat_subagents.types import AgentReadyData


class TestAgentRegistry(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.registry = AgentRegistry(runner_name="runner_a")

    async def test_register_local_agent(self):
        """Local agent is registered and appears in local_agents."""
        data = AgentReadyData(agent_name="greeter", runner="runner_a")
        result = await self.registry.register(data)

        self.assertTrue(result)
        self.assertIn("greeter", self.registry.local_agents)
        self.assertNotIn("greeter", self.registry.remote_agents)

    async def test_register_remote_agent(self):
        """Remote agent is registered and appears in remote_agents."""
        data = AgentReadyData(agent_name="support", runner="runner_b")
        result = await self.registry.register(data)

        self.assertTrue(result)
        self.assertIn("support", self.registry.remote_agents)
        self.assertNotIn("support", self.registry.local_agents)

    async def test_duplicate_registration_returns_false(self):
        """Registering the same agent twice returns False."""
        data = AgentReadyData(agent_name="greeter", runner="runner_a")
        first = await self.registry.register(data)
        second = await self.registry.register(data)

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(self.registry.local_agents.count("greeter"), 1)

    async def test_get_local_agent(self):
        """get() returns data for a local agent."""
        data = AgentReadyData(agent_name="greeter", runner="runner_a")
        await self.registry.register(data)

        result = self.registry.get("greeter")
        self.assertIs(result, data)

    async def test_get_remote_agent(self):
        """get() returns data for a remote agent."""
        data = AgentReadyData(agent_name="support", runner="runner_b")
        await self.registry.register(data)

        result = self.registry.get("support")
        self.assertIs(result, data)

    async def test_get_unknown_agent_returns_none(self):
        """get() returns None for an unknown agent."""
        self.assertIsNone(self.registry.get("nonexistent"))

    async def test_contains(self):
        """__contains__ works for registered and unregistered agents."""
        data = AgentReadyData(agent_name="greeter", runner="runner_a")
        await self.registry.register(data)

        self.assertIn("greeter", self.registry)
        self.assertNotIn("unknown", self.registry)

    async def test_watch_fires_on_registration(self):
        """Watch handler fires when the watched agent registers."""
        received = []

        async def handler(agent_data):
            received.append(agent_data)

        await self.registry.watch("greeter", handler)

        data = AgentReadyData(agent_name="greeter", runner="runner_a")
        await self.registry.register(data)

        self.assertEqual(len(received), 1)
        self.assertIs(received[0], data)

    async def test_watch_does_not_fire_for_other_agents(self):
        """Watch handler does not fire for a different agent."""
        received = []

        async def handler(agent_data):
            received.append(agent_data)

        await self.registry.watch("greeter", handler)

        data = AgentReadyData(agent_name="support", runner="runner_a")
        await self.registry.register(data)

        self.assertEqual(len(received), 0)

    async def test_watch_does_not_fire_on_duplicate(self):
        """Watch handler does not fire on duplicate registration."""
        received = []

        async def handler(agent_data):
            received.append(agent_data)

        await self.registry.watch("greeter", handler)

        data = AgentReadyData(agent_name="greeter", runner="runner_a")
        await self.registry.register(data)
        await self.registry.register(data)

        self.assertEqual(len(received), 1)

    async def test_multiple_watchers(self):
        """Multiple watch handlers fire for the same agent."""
        received_a = []
        received_b = []

        async def handler_a(agent_data):
            received_a.append(agent_data)

        async def handler_b(agent_data):
            received_b.append(agent_data)

        await self.registry.watch("greeter", handler_a)
        await self.registry.watch("greeter", handler_b)

        data = AgentReadyData(agent_name="greeter", runner="runner_a")
        await self.registry.register(data)

        self.assertEqual(len(received_a), 1)
        self.assertEqual(len(received_b), 1)

    async def test_watch_fires_immediately_if_already_registered(self):
        """Watch handler fires immediately when the agent is already registered."""
        data = AgentReadyData(agent_name="greeter", runner="runner_a")
        await self.registry.register(data)

        received = []

        async def handler(agent_data):
            received.append(agent_data)

        await self.registry.watch("greeter", handler)

        self.assertEqual(len(received), 1)
        self.assertIs(received[0], data)

    async def test_runner_name_property(self):
        """runner_name returns the name passed at construction."""
        self.assertEqual(self.registry.runner_name, "runner_a")

    async def test_multiple_remote_runners(self):
        """Agents from multiple remote runners are tracked separately."""
        data_b = AgentReadyData(agent_name="agent_b", runner="runner_b")
        data_c = AgentReadyData(agent_name="agent_c", runner="runner_c")
        await self.registry.register(data_b)
        await self.registry.register(data_c)

        remote = self.registry.remote_agents
        self.assertIn("agent_b", remote)
        self.assertIn("agent_c", remote)
        self.assertEqual(len(remote), 2)


if __name__ == "__main__":
    unittest.main()
