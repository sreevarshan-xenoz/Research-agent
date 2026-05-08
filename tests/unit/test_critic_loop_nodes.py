from __future__ import annotations

import pytest
from research_agent.orchestration.nodes import awaiting_user_critic_node

@pytest.mark.asyncio
async def test_awaiting_user_critic_node():
    state = {}  # GraphState is a TypedDict, but for this simple node, we can pass an empty dict
    result = await awaiting_user_critic_node(state)
    assert result == {"phase": "awaiting_critic_review"}
