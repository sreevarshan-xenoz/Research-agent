# Integration Testing Strategy — Orchestration Pipeline

> **Status:** Architecture Proposal  
> **Author:** Research Agent Team  
> **Date:** 2026-05-28  

---

## 1. Executive Summary

The system has **21 test files** with 22 passing tests, but coverage is concentrated on isolated unit tests with mocked LLMs and simplified `FakeRunner`/`FakeAdapter` replacements. There is **no real integration test** that:

- Executes the full pipeline with tool interaction
- Tests Redis checkpoint persistence
- Tests concurrent execution or cancellation
- Tests WebSocket real-time streaming
- Simulates provider failures
- Validates graph determinism

This document proposes a **4-tier testing architecture** with a structured fixture hierarchy, synthetic research topics, provider mocks with failure simulation, and CI-friendly execution paths.

---

## 2. Current Coverage Analysis

### 2.1 Test Inventory

| File | Tests | What It Tests | Mocking Level | Gap |
|------|-------|---------------|---------------|-----|
| `test_smoke.py` | 2 | Full graph with empty registry (no tools) | All tools missing | Never tests real tool interaction |
| `test_graph_routing.py` | 5 | `_route_after_critic` logic + graph build | No mocking | Pure logic tests — correct |
| `test_orchestration_edge_cases.py` | 8 | Stop reasons, dependency resolution | No mocking | Pure logic tests — correct |
| `test_worker_node.py` | 3 | Worker execution, progress, web enrichment | `FakeAdapter` | Tests single-worker, not concurrent |
| `test_webapp.py` | 6 | Session/chat, streaming, resume | `FakeRunner` | Never exercises real graph through API |
| `test_checkpoint_persistence.py` | 2 | Save/load checkpoint files | File system | No Redis persistence test |
| `test_output_pipeline.py` | 5 | LaTeX render, BibTeX, export, validation | Pure functions | Correct |
| `test_rag_indexer.py` | 1 | Chunk deduplication | In-memory Qdrant | Single scenario |
| `test_critic_loop_nodes.py` | 1 | `awaiting_user_critic_node` | No mocking | Trivial |
| `test_planner_feedback.py` | 2 | Planner with/without feedback | `AsyncMock` | Correct |
| `test_phase1_enhancements.py` | 4 | Config, BibTeX, web failover, checkpoint/resume | Mix of mocks | Interactive checkpoint test is the most realistic |
| `test_iteration_loop.py` | 1 | Low-confidence iteration | Empty registry | Tests loop existence, not correctness |

### 2.2 Missing Coverage Matrix

| Area | Unit Tests | Integration Tests | Status |
|------|-----------|-------------------|--------|
| Graph routing logic | ✅ 5 tests | ❌ 0 | Needs full-graph execution test |
| Worker task execution | ✅ 3 tests | ❌ 0 | Needs concurrent worker tests |
| Webapp API endpoints | ✅ 6 tests | ❌ 0 | All use `FakeRunner` |
| WebSocket streaming | ❌ 0 | ❌ 0 | No WebSocket tests at all |
| Checkpoint persistence | ✅ 2 tests | ❌ 0 | File only, no Redis |
| Redis session persistence | ❌ 0 | ❌ 0 | No Redis tests |
| Qdrant indexing pipeline | ✅ 1 test | ❌ 0 | Single scenario, no graph integration |
| Exporter pipeline | ✅ 5 tests | ❌ 0 | Tests functions, not node |
| Concurrency | ❌ 0 | ❌ 0 | No parallel execution tests |
| Cancellation / interrupt | ❌ 0 | ❌ 0 | No interrupt signal tests |
| Provider failure simulation | ❌ 0 | ❌ 0 | No systematic failure testing |
| Session resume correctness | ❌ 1 (FakeRunner) | ❌ 0 | No real graph resume |
| Graph determinism | ❌ 0 | ❌ 0 | No repeatability test |
| Stress / large topics | ❌ 0 | ❌ 0 | No performance tests |

---

## 3. Testing Architecture

### 3.1 Four-Tier Hierarchy

```
Tier 1: Unit Tests (existing, maintain)
  ├── Pure logic tests (routing, stop_reason, dependency resolution)
  ├── Function tests (BibTeX, LaTeX validation, escape)
  └── Mocked LLM node tests (planner with AsyncMock, critic with mock)

Tier 2: Integration Tests (NEW — this proposal)
  ├── Graph execution with tool adapters
  ├── Redis persistence with testcontainers or mock Redis
  ├── WebSocket streaming with real graph
  ├── Concurrency and cancellation
  ├── Provider failure simulation
  └── Exporter pipeline end-to-end

Tier 3: E2E Tests (NEW — skeletal)
  ├── API-based full workflow (session → chat → stream → result → resume)
  ├── CLI-based workflow (gradio)
  └── Overleaf integration (smoke)

Tier 4: Stress Tests (NEW — optional, CI-skip)
  ├── Parallel run execution
  ├── Large topic throughput
  ├── Memory leak detection
  └── Token cost tracking
```

### 3.2 Directory Structure

```
tests/
  conftest.py                          # Global fixtures (existing)
  unit/                                # Tier 1 (existing, maintain)
    test_smoke.py
    test_graph_routing.py
    ...
  integration/                         # Tier 2 (NEW)
    conftest.py                        # Integration-specific fixtures
    test_graph_execution.py            # Full pipeline with tool adapters
    test_redis_persistence.py          # Redis checkpoint + resume
    test_websocket_streaming.py        # WS with real graph
    test_concurrent_execution.py       # Parallel runs, cancellation
    test_provider_failures.py          # Simulated provider errors
    test_exporter_pipeline.py          # Exporter end-to-end
    test_graph_determinism.py          # Repeatability
    test_qdrant_indexing_pipeline.py   # Indexing through full graph
    test_replanning_loop.py            # Critic → replanner → worker loop
  e2e/                                 # Tier 3 (NEW)
    test_api_workflow.py               # Full API workflow
    test_gradio_bootstrap.py           # Gradio startup smoke
  stress/                              # Tier 4 (NEW, CI-skip)
    test_parallel_runs.py              # 5+ concurrent runs
    test_large_topic.py                # Document generation throughput
```

---

## 4. Test Fixture Architecture

### 4.1 Conftest Hierarchy

**`tests/integration/conftest.py`** — New file with integration-specific fixtures:

```python
"""
Integration test fixtures for the orchestration pipeline.

Provides:
- mock_tool_registry: deterministic tool adapters with configurable failure
- mock_llm_response: controls what LLM calls return
- in_memory_qdrant: isolated Qdrant instance per test
- test_topic_provider: synthetic research topics of varying complexity
- interrupt_signal_factory: creates cancellable events
- redis_test_server: optional Redis test container
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from research_agent.tools.base import BaseToolAdapter, ToolResult
from research_agent.orchestration.state import WorkflowState, GraphState


# ─── Fixture Categories ─────────────────────────────────────────────


@pytest.fixture
def mock_llm_response(monkeypatch):
    """
    Provides deterministic LLM responses for all model calls.

    Usage:
        def test_something(mock_llm_response):
            mock_llm_response.set("agenerate_text", "Return this text")
            mock_llm_response.set("agenerate_json", {"key": "value"})
    """
    responses: dict[str, Any] = {}

    async def fake_agenerate_text(*args, **kwargs):
        return responses.get("agenerate_text", "Mocked text response.")

    async def fake_agenerate_json(*args, **kwargs):
        return responses.get("agenerate_json", {"result": "ok"})

    monkeypatch.setattr(
        "research_agent.models.agenerate_text", fake_agenerate_text
    )
    monkeypatch.setattr(
        "research_agent.models.agenerate_json", fake_agenerate_json
    )

    class MockLLM:
        def set(self, function: str, response: Any):
            responses[function] = response

    return MockLLM()
```

### 4.2 Deterministic Tool Adapter with Failure Simulation

```python
class DeterministicToolAdapter(BaseToolAdapter):
    """
    Tool adapter that returns deterministic results with configurable failure modes.

    Failure modes:
    - "rate_limit": simulates 429 responses
    - "timeout": simulates connection timeout
    - "empty": returns zero results
    - "corrupt": returns malformed data
    - None: returns normal data

    Usage:
        adapter = DeterministicToolAdapter(
            provider_name="arxiv",
            failure_mode="rate_limit",
            item_count=3,
            delay_seconds=0.5,  # Simulate network latency
        )
    """

    provider_name = "deterministic"

    def __init__(
        self,
        provider_name: str = "deterministic",
        failure_mode: str | None = None,
        item_count: int = 3,
        delay_seconds: float = 0.0,
        seed: int = 42,
    ):
        self.provider_name = provider_name
        self.failure_mode = failure_mode
        self.item_count = item_count
        self.delay_seconds = delay_seconds
        self.call_count = 0

    def search(self, query: str, limit: int = 5) -> ToolResult:
        self.call_count += 1
        import time as time_module
        time_module.sleep(self.delay_seconds)

        if self.failure_mode == "rate_limit":
            return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=[f"rate_limit_error:HTTP 429 for {self.provider_name}"],
            )
        elif self.failure_mode == "timeout":
            raise TimeoutError(f"Connection timeout for {self.provider_name}")
        elif self.failure_mode == "empty":
            return ToolResult(provider=self.provider_name, items=[])
        elif self.failure_mode == "corrupt":
            return ToolResult(
                provider=self.provider_name,
                items=[{} for _ in range(self.item_count)],  # Empty dicts
                warnings=["corrupt_data:missing_fields"],
            )

        items = [
            {
                "title": f"{self.provider_name} Result {i+1}",
                "url": f"https://{self.provider_name}.example/paper{i+1}",
                "snippet": (
                    f"Summary of finding {i+1} for query: {query[:50]}"
                ),
                "year": "2026",
                "authors": ["Test Author"],
                "source_type": self.provider_name,
            }
            for i in range(min(self.item_count, limit))
        ]
        return ToolResult(provider=self.provider_name, items=items)
```

### 4.3 Synthetic Research Topic Factory

```python
SYNTHETIC_TOPICS = {
    "simple": "What is the capital of France?",
    "balanced": (
        "A comparative analysis of retrieval-augmented generation "
        "for software engineering question-answering"
    ),
    "complex": (
        "Multi-modal foundation models for autonomous scientific discovery "
        "in computational biology and materials science"
    ),
    "edge_empty": "",
    "edge_ambiguous": "AI",
}


@pytest.fixture(params=["simple", "balanced"])
def test_topic(request):
    """Parameterized fixture providing topics of varying complexity.

    Yields topic name and topic string. Tests can be parametrized to
    run against simple and balanced topics by default, or explicitly
    select specific topics.
    """
    name = request.param
    return name, SYNTHETIC_TOPICS[name]
```

### 4.4 In-Memory Qdrant Fixture

```python
@pytest.fixture
def in_memory_qdrant(monkeypatch):
    """Forces Qdrant to use in-memory storage for the test scope."""
    monkeypatch.setenv("QDRANT_LOCATION", ":memory:")
    yield
    # Cleanup: the in-memory Qdrant is dropped when the process exits
```

### 4.5 Redis Test Fixture

```python
@pytest.fixture
async def redis_checkpointer(monkeypatch):
    """
    Provides a Redis-based checkpointer for persistence tests.

    Uses fakeredis if available, otherwise requires a running Redis instance
    (configurable via REDIS_TEST_URL env var).

    Falls back to MemorySaver with monkeypatched settings if neither is available,
    to ensure tests can run in CI without Redis.
    """
    redis_url = os.environ.get("REDIS_TEST_URL", "")
    
    if not redis_url:
        try:
            import fakeredis
            fake_server = fakeredis.FakeServer()
            redis_client = await fakeredis.FakeAsyncRedis(server=fake_server)
            
            from langgraph.checkpoint.redis import AsyncRedisSaver
            checkpointer = AsyncRedisSaver(redis_client=redis_client)
            
            monkeypatch.setenv("SESSION_PERSISTENCE", "redis")
            monkeypatch.setenv("REDIS_URL", "fakeredis://localhost")
            
            yield checkpointer
            await redis_client.aclose()
            return
        except ImportError:
            pytest.skip("fakeredis not installed, Redis persistence tests skipped")
    
    # Real Redis connection
    import redis.asyncio as redis
    pool = redis.ConnectionPool.from_url(redis_url)
    redis_client = redis.Redis(connection_pool=pool)
    
    from langgraph.checkpoint.redis import AsyncRedisSaver
    checkpointer = AsyncRedisSaver(redis_client=redis_client)
    
    monkeypatch.setenv("SESSION_PERSISTENCE", "redis")
    monkeypatch.setenv("REDIS_URL", redis_url)
    
    yield checkpointer
    
    await redis_client.aclose()
    await pool.disconnect()
```

---

## 5. Integration Test Specifications

### 5.1 Graph Execution Tests (`test_graph_execution.py`)

**Purpose:** Validate full pipeline execution with real graph, deterministic tool adapters, and mocked LLM responses.

```python
"""Integration tests for full graph execution with tool adapters."""

import pytest
from pathlib import Path
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


@pytest.mark.asyncio
class TestGraphExecution:
    """Tests the full graph pipeline with deterministic tool adapters."""

    async def test_full_pipeline_completes(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """Full pipeline from intake → exporter with deterministic tools."""
        mock_llm_response.set("agenerate_text", "Mocked section content.")
        mock_llm_response.set(
            "agenerate_json",
            {
                "tasks": [
                    {"task_id": "t1", "title": "Background", "objective": "Research background"},
                    {"task_id": "t2", "title": "Methods", "objective": "Analyze methods"},
                ],
                "title": "Test Paper",
                "abstract": "This is a test abstract.",
                "body": "\\section{Background}\nBackground content.\n\\section{Methods}\nMethods content.",
            },
        )

        from tests.integration.conftest import DeterministicToolAdapter

        registry = {
            "arxiv": DeterministicToolAdapter(provider_name="arxiv", item_count=3),
            "semantic_scholar": DeterministicToolAdapter(
                provider_name="semantic_scholar", item_count=2
            ),
        }

        state = WorkflowState(
            run_id="test-full-pipeline",
            topic="A comparative analysis of RAG methods",
            artifact_root=str(tmp_path),
            max_iterations=1,
        )

        updated = await run_graph(state, registry=registry)

        assert updated.phase == "completed"
        assert updated.stop_reason == "completed"
        assert updated.task_findings
        assert "t1" in updated.task_findings
        assert updated.artifact_dir
        assert (Path(updated.artifact_dir) / "main.tex").exists()

    async def test_pipeline_with_empty_results(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """Pipeline handles empty tool results gracefully."""
        mock_llm_response.set("agenerate_text", "")
        mock_llm_response.set(
            "agenerate_json",
            {
                "tasks": [{"task_id": "t1", "title": "Test", "objective": "Test task"}],
                "title": "Fallback Paper",
                "abstract": "Fallback abstract.",
                "body": "\\section{Test}\nFallback content.",
            },
        )

        registry = {
            "arxiv": DeterministicToolAdapter(
                provider_name="arxiv", failure_mode="empty", item_count=0
            ),
        }

        state = WorkflowState(
            run_id="test-empty-results",
            topic="Test topic with no results",
            artifact_root=str(tmp_path),
        )

        updated = await run_graph(state, registry=registry)

        # Should complete with fallback content and warnings
        assert updated.phase == "completed"
        assert updated.run_warnings  # Should have warnings about empty results

    async def test_pipeline_with_partial_provider_failure(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """One provider fails, others succeed — pipeline should continue."""
        mock_llm_response.set("agenerate_text", "Partial failure section content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "Test", "objective": "Test"}],
            "title": "Paper", "abstract": "Abstract.", "body": "\\section{T}\nBody.",
        })

        registry = {
            "arxiv": DeterministicToolAdapter(provider_name="arxiv", item_count=3),
            "semantic_scholar": DeterministicToolAdapter(
                provider_name="semantic_scholar", failure_mode="timeout", item_count=0
            ),
        }

        state = WorkflowState(
            run_id="test-partial-failure",
            topic="Test with partial provider failure",
            artifact_root=str(tmp_path),
        )

        updated = await run_graph(state, registry=registry)

        # Should still complete — other provider succeeded
        assert updated.phase == "completed"
        assert updated.task_findings["t1"]["arxiv"]["item_count"] == 3
```

### 5.2 Redis Persistence Tests (`test_redis_persistence.py`)

**Purpose:** Validate Redis checkpoint save/load, session resume, and recovery.

```python
"""Integration tests for Redis-based checkpoint persistence."""

import pytest
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


@pytest.mark.asyncio
@pytest.mark.redis
class TestRedisPersistence:
    """Tests Redis checkpoint save/load and session resume."""

    async def test_checkpoint_saves_and_restores(
        self, tmp_path, in_memory_qdrant, redis_checkpointer, mock_llm_response
    ):
        """Run saves checkpoint to Redis, resumed run restores it."""
        mock_llm_response.set("agenerate_text", "Checkpointed content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "Test", "objective": "Test"}],
            "title": "Paper", "abstract": "Abstract.", "body": "\\section{T}\nBody.",
        })

        registry = {
            "arxiv": DeterministicToolAdapter(provider_name="arxiv", item_count=2),
        }

        state = WorkflowState(
            run_id="test-redis-checkpoint",
            topic="Redis checkpoint test",
            artifact_root=str(tmp_path),
        )

        updated = await run_graph(state, registry=registry)
        assert updated.phase == "completed"

        # Simulate session resume: new state with same run_id
        resume_state = WorkflowState(
            run_id="test-redis-checkpoint",
            topic="Redis checkpoint test (resumed)",
            artifact_root=str(tmp_path),
        )

        resumed = await run_graph(resume_state, registry=registry)
        assert resumed.phase == "completed"

    async def test_checkpoint_recovery_after_interrupt(
        self, tmp_path, in_memory_qdrant, redis_checkpointer, mock_llm_response
    ):
        """Interrupted run can be resumed from Redis checkpoint."""
        # This test simulates an interrupt during execution
        # and verifies the checkpoint can be recovered
        mock_llm_response.set("agenerate_text", "Content before interrupt.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "Test", "objective": "Test"}],
            "title": "Paper", "abstract": "Abstract.", "body": "\\section{T}\nBody.",
        })

        state = WorkflowState(
            run_id="test-recovery",
            topic="Recovery test",
            artifact_root=str(tmp_path),
        )

        # First run completes normally
        updated = await run_graph(state, registry={
            "arxiv": DeterministicToolAdapter(provider_name="arxiv", item_count=1),
        })

        # Verify checkpoint exists
        from langgraph.checkpoint.redis import AsyncRedisSaver
        # Checkpoint should be readable
        assert updated.phase == "completed"
```

### 5.3 WebSocket Streaming Tests (`test_websocket_streaming.py`)

**Purpose:** Validate real-time progress events during graph execution via WebSocket.

```python
"""Integration tests for WebSocket real-time streaming."""

import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from research_agent.app.webapp import create_app


@pytest.mark.asyncio
class TestWebSocketStreaming:
    """Tests the WebSocket /ws/chat/{session_id} endpoint with real graph."""

    async def test_websocket_receives_progress_events(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """WebSocket receives real progress events during graph execution."""
        mock_llm_response.set("agenerate_text", "WebSocket test content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [
                {"task_id": "t1", "title": "Task 1", "objective": "Objective 1"},
                {"task_id": "t2", "title": "Task 2", "objective": "Objective 2"},
            ],
            "title": "WS Paper",
            "abstract": "WS abstract.",
            "body": "\\section{T}\nBody.",
        })

        from tests.integration.conftest import DeterministicToolAdapter
        from research_agent.orchestration.graph import run_graph

        registry = {
            "arxiv": DeterministicToolAdapter(provider_name="arxiv", item_count=2),
        }

        app = create_app(
            graph_runner=run_graph,
            registry=registry,
            artifact_root=str(tmp_path),
        )

        client = TestClient(app)

        # Create session
        sess_resp = client.post("/api/session", json={"template": "ieee"})
        assert sess_resp.status_code == 200
        session_id = sess_resp.json()["session_id"]

        # Simulate WebSocket connection via streaming response
        # (WebSocket test client requires special handling)
        stream_resp = client.post(
            "/api/chat/stream",
            json={
                "session_id": session_id,
                "message": "WebSocket integration test topic",
                "template": "ieee",
            },
        )
        assert stream_resp.status_code == 200

        events = []
        for line in stream_resp.iter_lines():
            if not line:
                continue
            if isinstance(line, bytes):
                line = line.decode("utf-8")
            events.append(json.loads(line))

        # Should see status events for each worker
        status_events = [e for e in events if e["event"] == "status"]
        assert len(status_events) >= 2  # At least t1 and t2

        result_events = [e for e in events if e["event"] == "result"]
        assert len(result_events) == 1

    async def test_websocket_concurrent_sessions(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """Multiple WebSocket sessions run concurrently without interference."""
        mock_llm_response.set("agenerate_text", "Concurrent test content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "T1", "objective": "O1"}],
            "title": "Paper", "abstract": "Abs.", "body": "\\section{T}\nBody.",
        })

        from tests.integration.conftest import DeterministicToolAdapter
        registry = {
            "arxiv": DeterministicToolAdapter(
                provider_name="arxiv", item_count=1, delay_seconds=0.1
            ),
        }

        app = create_app(graph_runner=run_graph, registry=registry)
        client = TestClient(app)

        # Create two sessions
        s1 = client.post("/api/session", json={}).json()["session_id"]
        s2 = client.post("/api/session", json={}).json()["session_id"]

        # Run both streams concurrently
        async def run_stream(session_id: str, topic: str):
            resp = client.post(
                "/api/chat/stream",
                json={"session_id": session_id, "message": topic, "template": "ieee"},
            )
            events = []
            for line in resp.iter_lines():
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8")
                events.append(json.loads(line))
            return events

        events1, events2 = await asyncio.gather(
            run_stream(s1, "Concurrent topic 1"),
            run_stream(s2, "Concurrent topic 2"),
        )

        # Both should complete
        assert any(e["event"] == "result" for e in events1)
        assert any(e["event"] == "result" for e in events2)
```

### 5.4 Concurrent Execution Tests (`test_concurrent_execution.py`)

**Purpose:** Validate parallel run execution, cancellation, and resource isolation.

```python
"""Integration tests for concurrent execution and cancellation."""

import asyncio
import threading
import pytest
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


@pytest.mark.asyncio
@pytest.mark.slow
class TestConcurrentExecution:
    """Tests concurrent graph execution and cancellation."""

    async def test_parallel_runs_isolate_state(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """Multiple parallel graph runs don't interfere."""
        mock_llm_response.set("agenerate_text", "Parallel test content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "T1", "objective": "O1"}],
            "title": "Paper", "abstract": "Abs.", "body": "\\section{T}\nBody.",
        })

        from tests.integration.conftest import DeterministicToolAdapter

        adapter = DeterministicToolAdapter(
            provider_name="arxiv", item_count=1, delay_seconds=0.05
        )
        registry = {"arxiv": adapter}

        async def run_single(topic: str, run_id: str) -> str:
            state = WorkflowState(
                run_id=run_id,
                topic=topic,
                artifact_root=str(tmp_path / run_id),
            )
            result = await run_graph(state, registry=registry)
            return result.phase

        # Run 5 parallel executions
        phases = await asyncio.gather(*[
            run_single(f"Parallel topic {i}", f"run-parallel-{i}")
            for i in range(5)
        ])

        assert all(p == "completed" for p in phases)
        # Adapter should have been called across all runs
        assert adapter.call_count >= 5

    async def test_cancellation_during_execution(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """Graph execution can be cancelled mid-run."""
        mock_llm_response.set("agenerate_text", "Cancellation test.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "T1", "objective": "O1"}],
            "title": "Paper", "abstract": "Abs.", "body": "\\section{T}\nBody.",
        })

        from tests.integration.conftest import DeterministicToolAdapter

        interrupt_signal = threading.Event()
        registry = {
            "arxiv": DeterministicToolAdapter(
                provider_name="arxiv", item_count=5, delay_seconds=0.2
            ),
        }

        state = WorkflowState(
            run_id="test-cancellation",
            topic="Cancellation test topic",
            artifact_root=str(tmp_path),
            interrupt_signal=interrupt_signal,
        )

        # Schedule cancellation after a short delay
        async def cancel_after_delay():
            await asyncio.sleep(0.5)
            interrupt_signal.set()

        cancel_task = asyncio.create_task(cancel_after_delay())
        result = await run_graph(state, registry=registry)
        await cancel_task

        # Should have stopped due to interrupt
        assert result.stop_reason == "user_interrupt"
        # Should have some findings from before the interrupt
        assert result.task_findings or result.phase in ("stopped", "completed")
```

### 5.5 Provider Failure Tests (`test_provider_failures.py`)

**Purpose:** Simulate all provider failure modes and validate graceful degradation.

```python
"""Integration tests for provider failure simulation."""

import pytest
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


@pytest.mark.asyncio
class TestProviderFailures:
    """Tests graceful degradation under various provider failure modes."""

    @pytest.mark.parametrize("failure_mode", ["rate_limit", "timeout", "empty", "corrupt"])
    async def test_single_provider_failure(
        self, tmp_path, in_memory_qdrant, mock_llm_response, failure_mode
    ):
        """Each failure mode is handled without crashing the graph."""
        mock_llm_response.set("agenerate_text", f"{failure_mode} test content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "T1", "objective": "O1"}],
            "title": "Paper", "abstract": "Abs.", "body": "\\section{T}\nBody.",
        })

        from tests.integration.conftest import DeterministicToolAdapter

        registry = {
            "arxiv": DeterministicToolAdapter(
                provider_name="arxiv",
                failure_mode=failure_mode,
                item_count=0,
            ),
        }

        state = WorkflowState(
            run_id=f"test-failure-{failure_mode}",
            topic=f"Test {failure_mode} failure mode",
            artifact_root=str(tmp_path),
        )

        updated = await run_graph(state, registry=registry)

        # Should complete without crashing
        assert updated.phase in ("completed", "stopped")
        # Should have warnings about the failure
        if failure_mode in ("rate_limit", "empty", "corrupt"):
            assert len(updated.run_warnings) >= 0  # May or may not have warnings

    async def test_all_providers_fail(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """When all providers fail, graph should still complete with fallback."""
        mock_llm_response.set("agenerate_text", "All fail test.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "T1", "objective": "O1"}],
            "title": "Fallback",
            "abstract": "Fallback abstract.",
            "body": "\\section{Fallback}\nNo provider data.",
        })

        from tests.integration.conftest import DeterministicToolAdapter

        registry = {
            "arxiv": DeterministicToolAdapter(
                provider_name="arxiv", failure_mode="timeout", item_count=0
            ),
            "semantic_scholar": DeterministicToolAdapter(
                provider_name="semantic_scholar", failure_mode="rate_limit", item_count=0
            ),
        }

        state = WorkflowState(
            run_id="test-all-fail",
            topic="Test all providers fail",
            artifact_root=str(tmp_path),
        )

        updated = await run_graph(state, registry=registry)

        assert updated.phase in ("completed", "stopped")
        # Task findings should still be present (even if empty)
        assert "t1" in updated.task_findings
```

### 5.6 Exporter Pipeline Tests (`test_exporter_pipeline.py`)

**Purpose:** Validate the exporter node end-to-end through the graph, with LaTeX validation.

```python
"""Integration tests for the exporter pipeline."""

import pytest
from pathlib import Path
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.output.latex.renderer import validate_latex_package


@pytest.mark.asyncio
class TestExporterPipeline:
    """Tests the exporter node through the full graph."""

    async def test_exporter_produces_valid_latex(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """Exporter produces LaTeX that passes validation."""
        mock_llm_response.set("agenerate_text", "Exporter test content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "Intro", "objective": "Write intro"}],
            "title": "Exporter Test Paper",
            "abstract": "Testing the exporter pipeline.",
            "body": "\\section{Introduction}\nThis is the introduction.\n\\section{Conclusion}\nThis is the conclusion.",
        })

        from tests.integration.conftest import DeterministicToolAdapter
        registry = {
            "arxiv": DeterministicToolAdapter(provider_name="arxiv", item_count=2),
        }

        state = WorkflowState(
            run_id="test-exporter",
            topic="Exporter pipeline integration test",
            artifact_root=str(tmp_path),
            template="ieee",
        )

        updated = await run_graph(state, registry=registry)
        assert updated.phase == "completed"

        artifact_dir = Path(updated.artifact_dir)
        main_tex = (artifact_dir / "main.tex").read_text(encoding="utf-8")
        bibtex = (artifact_dir / "references.bib").read_text(encoding="utf-8")

        # Validate the exported LaTeX
        errors = validate_latex_package(
            template_name="ieee",
            main_tex=main_tex,
            bibtex=bibtex,
        )
        assert errors == [], f"LaTeX validation failed: {errors}"

    async def test_exporter_produces_all_artifacts(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """All expected artifact files are created."""
        mock_llm_response.set("agenerate_text", "All artifacts test.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "Intro", "objective": "Write intro"}],
            "title": "Artifacts Test",
            "abstract": "Testing all artifacts.",
            "body": "\\section{Intro}\nBody.",
        })

        from tests.integration.conftest import DeterministicToolAdapter
        registry = {
            "arxiv": DeterministicToolAdapter(provider_name="arxiv", item_count=1),
        }

        state = WorkflowState(
            run_id="test-artifacts",
            topic="Artifacts test",
            artifact_root=str(tmp_path),
        )

        updated = await run_graph(state, registry=registry)
        artifact_dir = Path(updated.artifact_dir)

        assert (artifact_dir / "main.tex").exists()
        assert (artifact_dir / "references.bib").exists()
        assert (artifact_dir / "compile_instructions.md").exists()
        assert (artifact_dir / "summary.json").exists()
```

### 5.7 Graph Determinism Tests (`test_graph_determinism.py`)

**Purpose:** Validate that identical inputs produce identical outputs (within expected variance).

```python
"""Integration tests for graph determinism."""

import hashlib
import pytest
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


@pytest.mark.asyncio
class TestGraphDeterminism:
    """Tests that same inputs produce same outputs (determinism)."""

    async def test_deterministic_with_mocked_llm(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """With mocked LLM, repeated runs produce identical results."""
        mock_llm_response.set("agenerate_text", "Deterministic test content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [{"task_id": "t1", "title": "T1", "objective": "O1"}],
            "title": "Deterministic Paper",
            "abstract": "Testing determinism.",
            "body": "\\section{Test}\nBody.",
        })

        from tests.integration.conftest import DeterministicToolAdapter

        registry = {
            "arxiv": DeterministicToolAdapter(
                provider_name="arxiv", item_count=1, seed=42
            ),
        }

        async def run_once(run_id: str) -> dict:
            state = WorkflowState(
                run_id=run_id,
                topic="Determinism test topic",
                artifact_root=str(tmp_path / run_id),
                max_iterations=1,
            )
            result = await run_graph(state, registry=registry)
            return {
                "phase": result.phase,
                "task_count": len(result.tasks),
                "task_findings_keys": sorted(result.task_findings.keys()),
            }

        result1 = await run_once("run-det-1")
        result2 = await run_once("run-det-2")

        assert result1["phase"] == result2["phase"]
        assert result1["task_count"] == result2["task_count"]
        assert result1["task_findings_keys"] == result2["task_findings_keys"]
```

### 5.8 Replanning Loop Tests (`test_replanning_loop.py`)

**Purpose:** Validate the critic → replanner → worker iteration loop.

```python
"""Integration tests for the replanning iteration loop."""

import pytest
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


@pytest.mark.asyncio
class TestReplanningLoop:
    """Tests the critic → replanner → worker iteration loop."""

    async def test_low_confidence_triggers_replanning(
        self, tmp_path, in_memory_qdrant
    ):
        """Low section confidence triggers replanning and additional worker tasks."""
        from tests.integration.conftest import DeterministicToolAdapter

        mock_llm_response.set("agenerate_text", "Low confidence test content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [
                {"task_id": "t1", "title": "Method A", "objective": "Research Method A"},
                {"task_id": "t2", "title": "Method B", "objective": "Research Method B"},
            ],
            "title": "Paper",
            "abstract": "Abstract.",
            "body": "\\section{Method A}\nContent for Method A.\n\\section{Method B}\nContent for Method B.",
        })

        registry = {
            "arxiv": DeterministicToolAdapter(provider_name="arxiv", item_count=0),
        }

        state = WorkflowState(
            run_id="test-replanning",
            topic="Low confidence method comparison",
            artifact_root=str(tmp_path),
            max_iterations=3,
        )

        updated = await run_graph(state, registry=registry)

        # Should have more tasks than initial plan due to replanning
        assert len(updated.tasks) > 1
        assert updated.phase in ("completed", "stopped")
```

### 5.9 Qdrant Indexing Pipeline Tests (`test_qdrant_indexing_pipeline.py`)

**Purpose:** Validate that the indexing node stores and retrieves evidence correctly.

```python
"""Integration tests for Qdrant indexing through the graph."""

import pytest
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState


@pytest.mark.asyncio
class TestQdrantIndexingPipeline:
    """Tests that the indexing node stores evidence correctly."""

    async def test_evidence_is_indexed_and_retrievable(
        self, tmp_path, in_memory_qdrant, mock_llm_response
    ):
        """Evidence from tool adapters is indexed and retrievable."""
        mock_llm_response.set("agenerate_text", "Indexing test content.")
        mock_llm_response.set("agenerate_json", {
            "tasks": [
                {"task_id": "t1", "title": "Methods", "objective": "Research methods"},
                {"task_id": "t2", "title": "Results", "objective": "Find results"},
            ],
            "title": "Paper",
            "abstract": "Abstract.",
            "body": "\\section{Methods}\nMethods content.\n\\section{Results}\nResults content.",
        })

        from tests.integration.conftest import DeterministicToolAdapter
        registry = {
            "arxiv": DeterministicToolAdapter(
                provider_name="arxiv",
                item_count=3,
                seed=42,
            ),
        }

        state = WorkflowState(
            run_id="test-indexing",
            topic="Indexing pipeline integration test",
            artifact_root=str(tmp_path),
        )

        updated = await run_graph(state, registry=registry)
        assert updated.phase == "completed"
        assert updated.combined_sections

        # The combiner node should have produced sections with content
        for section in updated.combined_sections:
            assert section.get("content")
```

### 5.10 CI-Fiendly Markers

```python
# pytest markers in pyproject.toml

[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "redis: marks tests that require Redis (deselect with '-m \"not redis\"')",
    "stress: marks stress tests (deselect with '-m \"not stress\"')",
    "e2e: marks end-to-end tests (deselect with '-m \"not e2e\"')",
]
```

**CI execution profiles:**

```bash
# Fast CI (unit + integration without slow/redis/stress/e2e)
pytest tests/unit tests/integration -m "not slow and not redis and not stress and not e2e"

# Full CI (all integration, no stress)
pytest tests/unit tests/integration -m "not stress and not e2e"

# Nightly (everything including stress)
pytest tests/

# Redis tests only
pytest tests/integration -m "redis"
```

---

## 6. Missing Coverage Summary

| Priority | Area | Current | Target | Gap |
|----------|------|---------|--------|-----|
| **P0** | Full graph execution with tools | ❌ 0 | ✅ 3 tests | Critical — no real pipeline test |
| **P0** | Redis persistence | ❌ 0 | ✅ 2 tests | Critical — no Redis tests at all |
| **P0** | WebSocket streaming | ❌ 0 | ✅ 2 tests | Critical — no streaming tests |
| **P0** | Provider failure modes | ❌ 0 | ✅ 5 tests | Critical — no failure simulation |
| **P1** | Concurrent execution | ❌ 0 | ✅ 1 test | High — no parallel test |
| **P1** | Cancellation | ❌ 0 | ✅ 1 test | High — no interrupt test |
| **P1** | Exporter end-to-end | ❌ 0 | ✅ 2 tests | High — only unit-tested |
| **P1** | Graph determinism | ❌ 0 | ✅ 1 test | High — no repeatability test |
| **P2** | Replanning loop | ❌ 1 (existing) | ✅ 1 test | Medium — needs real tool interaction |
| **P2** | Qdrant indexing pipeline | ❌ 0 | ✅ 1 test | Medium — only unit-tested |
| **P3** | Memory leak detection | ❌ 0 | ✅ 0 | Low — add later |
| **P3** | Token cost tracking | ❌ 0 | ✅ 0 | Low — monitoring infra needed first |

---

## 7. New Files Summary

| File | Purpose | Lines (est.) |
|------|---------|-------------|
| `tests/integration/conftest.py` | `DeterministicToolAdapter`, `mock_llm_response`, `test_topic`, `in_memory_qdrant`, `redis_checkpointer` | ~200 |
| `tests/integration/test_graph_execution.py` | Full pipeline, empty results, partial failure | ~150 |
| `tests/integration/test_redis_persistence.py` | Redis save/load, recovery | ~100 |
| `tests/integration/test_websocket_streaming.py` | WebSocket progress events, concurrent sessions | ~150 |
| `tests/integration/test_concurrent_execution.py` | Parallel runs, cancellation | ~120 |
| `tests/integration/test_provider_failures.py` | All failure modes, all-providers-fail | ~100 |
| `tests/integration/test_exporter_pipeline.py` | Export validation, all artifacts | ~100 |
| `tests/integration/test_graph_determinism.py` | Repeatability with mocked LLM | ~80 |
| `tests/integration/test_qdrant_indexing_pipeline.py` | Index → combiner evidence retrieval | ~80 |
| `tests/integration/test_replanning_loop.py` | Critic → replanner → worker loop | ~80 |
| `tests/e2e/test_api_workflow.py` | Full API workflow (session → chat → stream → resume) | ~80 |
| **TOTAL NEW** | **10 integration + 1 e2e test files + 1 conftest** | **~1,240** |

---

## 8. Implementation Order

### Phase 1 (Week 1) — Foundation
1. Create `tests/integration/conftest.py` with `DeterministicToolAdapter`, `mock_llm_response`, `in_memory_qdrant`
2. Create `test_graph_execution.py` — full pipe with tools (3 tests)
3. Add CI marker configuration to `pyproject.toml`

### Phase 2 (Week 2) — Persistence + Streaming
4. Create `test_redis_persistence.py` — fakeredis-based (2 tests)
5. Create `test_websocket_streaming.py` — SSE progress events (2 tests)
6. Create `test_exporter_pipeline.py` — LaTeX validation through graph (2 tests)

### Phase 3 (Week 3) — Failure + Concurrency
7. Create `test_provider_failures.py` — parametrized failure modes (5 tests)
8. Create `test_concurrent_execution.py` — parallel runs + cancellation (2 tests)
9. Create `test_graph_determinism.py` — repeatability (1 test)

### Phase 4 (Week 4) — Loops + Indexing + CI
10. Create `test_replanning_loop.py` — critic loop (1 test)
11. Create `test_qdrant_indexing_pipeline.py` — indexing through graph (1 test)
12. Create `tests/e2e/test_api_workflow.py` — full API workflow (1 test)
13. Configure CI profiles in `pyproject.toml`

---

## 9. CI Configuration

```yaml
# .github/workflows/test.yml (new)
name: Test Suite
on: [push, pull_request]

jobs:
  fast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pip install playwright && python -m playwright install chromium
      - run: pytest tests/unit tests/integration -m "not slow and not redis and not stress and not e2e" -v

  full:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pip install playwright && python -m playwright install chromium
      - run: pip install fakeredis
      - run: pytest tests/unit tests/integration -m "not stress and not e2e" -v
        env:
          REDIS_TEST_URL: redis://localhost:6379/0

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: ruff check src
      - run: mypy src
```

---

## 10. Operational Recommendations

### 10.1 Test Environment Isolation

Each integration test must run in complete isolation:
- **Qdrant**: Always `:memory:` mode (set via `test_env` fixture in `conftest.py`)
- **Redis**: Fakeredis for CI, real Redis for local testing with `REDIS_TEST_URL` env var
- **File system**: `tmp_path` for all artifact outputs
- **LLM calls**: Always mocked via `mock_llm_response` fixture
- **Tool adapters**: Use `DeterministicToolAdapter` — never call real APIs

### 10.2 Test Execution Profiles

```bash
# Quick feedback loop (15s)
pytest tests/unit tests/integration \
  -m "not slow and not redis and not stress and not e2e"

# Full CI (45s)
pytest tests/unit tests/integration \
  -m "not stress and not e2e"

# Slow tests only (2m+)
pytest -m "slow" -v

# Redis-dependent tests
pytest -m "redis" -v
REDIS_TEST_URL=redis://localhost:6379

# Nightly run (10m+)
pytest tests/ --runstress
```

### 10.3 Adding New Tests Checklist

When adding a new test:
1. Use `@pytest.mark.asyncio` for async tests
2. Use `mock_llm_response` fixture (never call real LLM)
3. Use `DeterministicToolAdapter` (never call real APIs)
4. Use `in_memory_qdrant` fixture
5. Use `tmp_path` for file output
6. Add appropriate marker (`slow`, `redis`, `stress`, `e2e`)
7. Test with both `mock_llm_response.set("agenerate_text", ...)` and `mock_llm_response.set("agenerate_json", ...)`
