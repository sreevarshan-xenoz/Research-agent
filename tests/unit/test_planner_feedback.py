from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from research_agent.orchestration.nodes.planner import planner_node
from research_agent.orchestration.state import GraphState

@pytest.mark.asyncio
async def test_planner_node_incorporates_feedback():
    state: GraphState = {
        "run_id": "test-run",
        "topic": "AI safety",
        "depth": "balanced",
        "critic_user_feedback": "Focus more on alignment research.",
        "tasks": [],
        "phase": "intake",
        # ... other required keys
    }
    
    # Mocking agenerate_json and apublish_progress
    with patch("research_agent.orchestration.nodes.planner.agenerate_json", new_callable=AsyncMock) as mock_gen, \
         patch("research_agent.orchestration.nodes.planner.apublish_progress", new_callable=AsyncMock) as mock_pub:
        
        mock_gen.return_value = {
            "tasks": [
                {"task_id": "t1", "title": "Alignment Research", "objective": "Research alignment"}
            ]
        }
        
        result = await planner_node(state)
        
        # Verify prompt injection
        args, kwargs = mock_gen.call_args
        prompt = kwargs["prompt"]
        assert "USER FEEDBACK FROM PREVIOUS ITERATION:" in prompt
        assert "Focus more on alignment research." in prompt
        
        # Verify result
        assert result["phase"] == "planning_complete"
        assert result["critic_user_feedback"] is None
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["task_id"] == "t1"

@pytest.mark.asyncio
async def test_planner_node_no_feedback():
    state: GraphState = {
        "run_id": "test-run",
        "topic": "AI safety",
        "depth": "balanced",
        "critic_user_feedback": None,
        "tasks": [],
        "phase": "intake",
    }
    
    with patch("research_agent.orchestration.nodes.planner.agenerate_json", new_callable=AsyncMock) as mock_gen, \
         patch("research_agent.orchestration.nodes.planner.apublish_progress", new_callable=AsyncMock) as mock_pub:
        
        mock_gen.return_value = {"tasks": []}
        
        await planner_node(state)
        
        args, kwargs = mock_gen.call_args
        prompt = kwargs["prompt"]
        assert "USER FEEDBACK FROM PREVIOUS ITERATION:" not in prompt
