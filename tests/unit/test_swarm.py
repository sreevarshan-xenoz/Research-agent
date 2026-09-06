"""Unit tests for Multi-Agent Research Swarm (P34)."""

import pytest
from httpx import ASGITransport, AsyncClient

from research_agent.app.webapp import create_app
from research_agent.orchestration.nodes.swarm_node import swarm_node
from research_agent.orchestration.state import GraphState
from research_agent.swarm.agents import SwarmAgent, ROLE_PERSONAS
from research_agent.swarm.consensus import (
    calculate_consensus_score,
    extract_agreed_and_disputed_claims,
    synthesize_swarm_consensus,
)
from research_agent.swarm.coordinator import SwarmCoordinator
from research_agent.swarm.models import (
    AgentContribution,
    DebateRound,
    DebateSession,
    SwarmConsensus,
    SwarmRole,
)


def test_swarm_models_serialization() -> None:
    """Test serialization and deserialization of swarm data models."""
    contrib = AgentContribution(
        agent_id="theo_01",
        role=SwarmRole.THEORIST,
        argument="Formal convergence requires bounded variance.",
        key_claims=["Claim 1", "Claim 2"],
        confidence=0.85,
    )
    data = contrib.to_dict()
    assert data["role"] == "theorist"
    assert data["confidence"] == 0.85

    restored = AgentContribution.from_dict(data)
    assert restored.agent_id == "theo_01"
    assert restored.role == SwarmRole.THEORIST
    assert len(restored.key_claims) == 2

    round_obj = DebateRound(
        round_number=1,
        phase="proposition",
        contributions=[contrib],
    )
    r_data = round_obj.to_dict()
    r_restored = DebateRound.from_dict(r_data)
    assert r_restored.round_number == 1
    assert len(r_restored.contributions) == 1

    consensus = SwarmConsensus(
        topic="Sample Topic",
        status="consensus_reached",
        consensus_score=0.88,
        synthesized_hypothesis="Synthesized hypothesis",
        theoretical_foundation="Formal bounds",
    )
    c_data = consensus.to_dict()
    c_restored = SwarmConsensus.from_dict(c_data)
    assert c_restored.status == "consensus_reached"
    assert c_restored.consensus_score == 0.88


@pytest.mark.asyncio
async def test_swarm_agents_proposition_and_critique() -> None:
    """Test agent proposition, cross-critique, and rebuttal."""
    theorist = SwarmAgent(role=SwarmRole.THEORIST)
    experimentalist = SwarmAgent(role=SwarmRole.EXPERIMENTALIST)
    critic = SwarmAgent(role=SwarmRole.CRITIC)

    topic = "Quantum Error Correction in Neutral Atom Arrays"

    # 1. Propose
    p_theo = await theorist.propose(topic)
    p_exp = await experimentalist.propose(topic)
    assert p_theo.role == SwarmRole.THEORIST
    assert p_theo.argument
    assert p_exp.role == SwarmRole.EXPERIMENTALIST

    # 2. Critique
    critiques = await critic.critique(topic, [p_theo, p_exp])
    assert isinstance(critiques, list)
    assert len(critiques) >= 1

    # 3. Rebut & Refine
    refined = await theorist.rebut_and_refine(topic, p_theo, critiques)
    assert refined.role == SwarmRole.THEORIST
    assert refined.argument


def test_consensus_scoring_and_claim_extraction() -> None:
    """Test consensus scoring math and claim extraction."""
    c1 = AgentContribution(
        agent_id="a1",
        role=SwarmRole.THEORIST,
        argument="Theory is sound",
        key_claims=["Convergence rate is O(1/t)", "Stability holds"],
        confidence=0.9,
        concessions=["Minor boundary adjustment"],
    )
    c2 = AgentContribution(
        agent_id="a2",
        role=SwarmRole.EXPERIMENTALIST,
        argument="Empirical results confirm",
        key_claims=["Benchmark shows 25% speedup", "Ablation confirms component A"],
        confidence=0.85,
    )
    critiques = [
        {"target_role": "theorist", "critique_point": "Convergence rate assumption", "severity": "moderate"}
    ]

    score = calculate_consensus_score([c1, c2], critiques)
    assert 0.0 <= score <= 1.0
    assert score > 0.5

    agreed, disputed, dissenting = extract_agreed_and_disputed_claims([c1, c2], critiques)
    assert isinstance(agreed, list)
    assert isinstance(disputed, list)


@pytest.mark.asyncio
async def test_coordinator_full_debate_session() -> None:
    """Test SwarmCoordinator multi-round debate execution."""
    coordinator = SwarmCoordinator(
        roles=["theorist", "experimentalist", "critic", "editor"],
        max_rounds=2,
        consensus_threshold=0.70,
    )

    topic = "Retrieval-Augmented Diffusion for Protein Structure Generation"
    session = await coordinator.run_debate(topic=topic, context="Context from literature search")

    assert session.session_id.startswith("swarm_")
    assert session.topic == topic
    assert len(session.rounds) == 2
    assert session.consensus is not None
    assert session.consensus.status in ["consensus_reached", "majority_agreement", "dissent_recorded"]
    assert session.consensus.synthesized_hypothesis
    assert session.consensus.theoretical_foundation


def test_coordinator_task_allocation() -> None:
    """Test dynamic task allocation to matching swarm roles."""
    coordinator = SwarmCoordinator()
    assert coordinator.allocate_task("Mathematical proof of error bounds") == SwarmRole.THEORIST
    assert coordinator.allocate_task("Benchmark evaluation on ImageNet") == SwarmRole.EXPERIMENTALIST
    assert coordinator.allocate_task("Adversarial bias and limitation analysis") == SwarmRole.CRITIC
    assert coordinator.allocate_task("Clinical trial domain deployment") == SwarmRole.DOMAIN_EXPERT
    assert coordinator.allocate_task("Literature review introduction") == SwarmRole.EDITOR


@pytest.mark.asyncio
async def test_swarm_graph_node() -> None:
    """Test swarm_node execution within GraphState."""
    state: GraphState = {
        "run_id": "test-swarm-run",
        "topic": "Graph Neural Networks for Drug Discovery",
        "template": "ieee",
        "phase": "planned",
        "iteration_index": 0,
        "stop_reason": None,
        "tasks": [],
        "section_confidence": {},
        "clarification_questions": [],
        "needs_clarification": False,
        "task_findings": {},
        "critic_notes": [],
        "combined_sections": [],
        "citations": [],
        "latex_main": "",
        "bibtex": "",
        "artifact_root": "artifacts",
        "artifact_dir": "",
        "run_warnings": [],
        "generated_hypotheses": [
            {"hypothesis": "Message passing scales sub-linearly", "rationale": "Sparse adjacency"}
        ],
        "swarm_session": None,
        "swarm_consensus": None,
    }

    result = await swarm_node(state)
    assert "swarm_session" in result
    assert "swarm_consensus" in result
    if result["swarm_session"]:
        assert result["swarm_session"]["topic"] == state["topic"]
        assert result["swarm_consensus"]["consensus_score"] >= 0.0


@pytest.mark.asyncio
async def test_swarm_api_routes() -> None:
    """Test Swarm REST endpoints."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /api/swarm/roles
        r_roles = await client.get("/api/swarm/roles")
        assert r_roles.status_code == 200
        data_roles = r_roles.json()
        assert data_roles["status"] == "success"
        assert len(data_roles["roles"]) >= 4

        # 2. GET /api/swarm/health
        r_health = await client.get("/api/swarm/health")
        assert r_health.status_code == 200
        data_health = r_health.json()
        assert data_health["status"] == "healthy"

        # 3. POST /api/swarm/debate
        r_debate = await client.post(
            "/api/swarm/debate",
            json={
                "topic": "Self-Supervised Learning on Single-Cell RNA Sequences",
                "max_rounds": 2,
                "consensus_threshold": 0.70,
            },
        )
        assert r_debate.status_code == 200
        data_debate = r_debate.json()
        assert data_debate["status"] == "success"
        assert data_debate["session"]["consensus"] is not None

        # 4. POST /api/swarm/synthesize
        r_synth = await client.post(
            "/api/swarm/synthesize",
            json={
                "topic": "Transformer Attention Complexity",
                "arguments": [
                    {
                        "role": "theorist",
                        "argument": "Linear attention approximates quadratic with kernel trick.",
                        "key_claims": ["O(N) complexity achieved"],
                    },
                    {
                        "role": "experimentalist",
                        "argument": "Throughput increases 3x with negligible perplexity degradation.",
                        "key_claims": ["3x speedup on 32k context"],
                    },
                ],
            },
        )
        assert r_synth.status_code == 200
        data_synth = r_synth.json()
        assert data_synth["status"] == "success"
        assert data_synth["consensus"]["consensus_score"] > 0
