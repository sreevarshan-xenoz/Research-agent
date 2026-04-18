from __future__ import annotations

import httpx
import types

from research_agent.tools.arxiv import ArxivAdapter
from research_agent.tools.browser_use import BrowserUseAdapter
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


def test_browser_use_falls_back_to_web_scraping_when_playwright_missing(monkeypatch) -> None:
    search_html = """
<html>
    <body>
        <a class="result__a" href="https://example.com/a">Result A</a>
        <div class="result__snippet">Snippet A</div>
    </body>
</html>
""".strip()

    page_html = """
<html>
    <head><meta name="description" content="Page meta description" /></head>
    <body>Full page text</body>
</html>
""".strip()

    def handler(request: httpx.Request) -> httpx.Response:
        if "duckduckgo.com" in str(request.url):
            return httpx.Response(200, text=search_html)
        if "example.com" in str(request.url):
            return httpx.Response(200, text=page_html)
        return httpx.Response(404)

    monkeypatch.setitem(__import__("sys").modules, "playwright.sync_api", None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = BrowserUseAdapter(client=client)

    result = adapter.search("agent systems", limit=2)

    assert result.items
    assert result.items[0]["url"] == "https://example.com/a"
    assert result.items[0]["source_type"] == "web_scrape"
    assert any(warning.startswith("browser_use_error:") for warning in result.warnings)


def test_browser_use_sdk_path_returns_browser_items(monkeypatch) -> None:
    class FakeHistory:
        def final_result(self) -> str:
            return (
                '[{"title":"Site A","url":"https://example.com/a","snippet":"Snippet A"},'
                '{"title":"Site B","url":"https://example.com/b","snippet":"Snippet B"}]'
            )

    class FakeAgent:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            self.kwargs = kwargs

        def run_sync(self, max_steps: int = 10):  # noqa: ANN201
            assert max_steps >= 8
            return FakeHistory()

    class FakeChatBrowserUse:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            self.kwargs = kwargs

    class FakeChatOpenAI:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            self.kwargs = kwargs

    class FakeBrowser:
        def __init__(self, **kwargs) -> None:  # noqa: ANN003
            self.kwargs = kwargs

    fake_module = types.SimpleNamespace(
        Agent=FakeAgent,
        Browser=FakeBrowser,
        ChatBrowserUse=FakeChatBrowserUse,
        ChatOpenAI=FakeChatOpenAI,
    )
    monkeypatch.setitem(__import__("sys").modules, "browser_use", fake_module)
    monkeypatch.setenv("BROWSER_USE_API_KEY", "test-key")

    adapter = BrowserUseAdapter(client=httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(404))))
    result = adapter.search("agent browser search", limit=2)

    assert len(result.items) == 2
    assert result.items[0]["source_type"] == "browser"
    assert result.metadata.get("browser_method") == "browser_use_sdk"


def test_browser_use_scrape_only_mode_skips_browser_attempts(monkeypatch) -> None:
    search_html = """
<html>
    <body>
        <a class="result__a" href="https://example.com/free">Free Result</a>
        <div class="result__snippet">Free snippet</div>
    </body>
</html>
""".strip()

    def handler(request: httpx.Request) -> httpx.Response:
        if "duckduckgo.com" in str(request.url):
            return httpx.Response(200, text=search_html)
        return httpx.Response(200, text="<html></html>")

    monkeypatch.setitem(__import__("sys").modules, "playwright.sync_api", None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = BrowserUseAdapter(
        browser_enabled=False,
        provider_name="web_scrape",
        client=client,
    )

    result = adapter.search("free search", limit=1)

    assert result.provider == "web_scrape"
    assert result.items
    assert result.items[0]["source_type"] == "web_scrape"
    assert result.metadata.get("browser_enabled") is False
    assert result.metadata.get("browser_method") == "disabled"
    assert not any(warning.startswith("browser_use_error:") for warning in result.warnings)
