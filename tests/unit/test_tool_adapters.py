from __future__ import annotations

import httpx

from research_agent.tools.arxiv import ArxivAdapter
from research_agent.tools.semantic_scholar import SemanticScholarAdapter
from research_agent.tools.web_search import WebSearchAdapter


def test_web_search_missing_key_returns_warning() -> None:
    adapter = WebSearchAdapter(api_key=None)
    result = adapter.search("agentic ai", limit=3)
    assert not result.items
    assert "missing_tavily_api_key" in result.warnings


def test_arxiv_adapter_parses_atom_feed() -> None:
    xml_feed = """
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/1234.5678</id>
    <title>Test Paper</title>
    <summary>Paper abstract text.</summary>
    <published>2026-01-01T00:00:00Z</published>
  </entry>
</feed>
""".strip()

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        return httpx.Response(200, text=xml_feed)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = ArxivAdapter(client=client)
    result = adapter.search("test", limit=1)

    assert len(result.items) == 1
    assert result.items[0]["title"] == "Test Paper"
    assert result.items[0]["source_type"] == "paper"


def test_semantic_scholar_normalizes_data() -> None:
    payload = {
        "data": [
            {
                "paperId": "abc123",
                "title": "A Benchmark Paper",
                "url": "https://example.org/paper",
                "year": 2025,
                "citationCount": 42,
                "abstract": "This is an abstract.",
                "authors": [{"name": "Author One"}, {"name": "Author Two"}],
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = SemanticScholarAdapter(api_key=None, client=client)
    result = adapter.search("benchmark", limit=1)

    assert len(result.items) == 1
    assert result.items[0]["paper_id"] == "abc123"
    assert result.items[0]["authors"] == ["Author One", "Author Two"]
