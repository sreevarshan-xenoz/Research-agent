import pytest
from research_agent.orchestration.nodes.citation_graph import CitationGraph


def test_citation_graph_empty():
    graph = CitationGraph()
    result = graph.build([])
    assert result == {"nodes": [], "edges": []}


def test_citation_graph_with_papers():
    graph = CitationGraph()
    papers = [
        {
            "id": "paper1",
            "title": "Deep Learning",
            "citations": ["paper2"],
        },
        {
            "id": "paper2",
            "title": "Earlier Work",
            "citations": [],
        },
    ]
    result = graph.build(papers)
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 1
    assert result["edges"][0]["source"] == "paper2"
    assert result["edges"][0]["target"] == "paper1"


def test_citation_graph_with_references_field():
    graph = CitationGraph()
    papers = [
        {
            "title": "Paper A",
            "references": [{"title": "Ref 1", "id": "ref1"}],
        },
    ]
    result = graph.build(papers)
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 1
