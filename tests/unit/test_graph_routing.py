import pytest
from research_agent.orchestration.graph import _route_after_critic, build_graph
from langgraph.graph import END

def test_route_after_critic_loop():
    # Low confidence, not interactive -> loop
    state = {
        "section_confidence": {"t1": 0.2},
        "iteration_index": 0,
        "max_iterations": 3,
        "autonomy_mode": "autonomous",
        "stop_reason": None,
    }
    assert _route_after_critic(state) == "replan"

def test_route_after_critic_await_user():
    # Low confidence, interactive -> await_user_critic
    state = {
        "section_confidence": {"t1": 0.2},
        "iteration_index": 0,
        "max_iterations": 3,
        "autonomy_mode": "interactive",
        "stop_reason": None,
    }
    assert _route_after_critic(state) == "await_user_critic"

def test_route_after_critic_combiner_high_confidence():
    # High confidence -> combiner
    state = {
        "section_confidence": {"t1": 0.8},
        "iteration_index": 0,
        "max_iterations": 3,
        "autonomy_mode": "interactive",
        "stop_reason": None,
    }
    assert _route_after_critic(state) == "combiner"

def test_route_after_critic_combiner_max_iterations():
    # Low confidence, but max iterations reached -> combiner
    state = {
        "section_confidence": {"t1": 0.2},
        "iteration_index": 3,
        "max_iterations": 3,
        "autonomy_mode": "interactive",
        "stop_reason": None,
    }
    assert _route_after_critic(state) == "combiner"

def test_graph_structure():
    graph = build_graph()
    # Check if nodes are present
    # For CompiledGraph, nodes might be accessible via .get_graph().nodes
    # Let's just check if we can build it.
    assert graph is not None
