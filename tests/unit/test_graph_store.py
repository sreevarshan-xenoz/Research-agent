from __future__ import annotations

from research_agent.rag.graph_store import KnowledgeGraphStore


def test_graph_persists_entities_and_relations(tmp_path):
    store = KnowledgeGraphStore(persist_dir=tmp_path)
    paper = store.add_entity("Paper One", "Paper", {"year": 2024})
    method = store.add_entity("Graph-RAG", "Method")
    store.add_relation(paper, method, "uses")
    store.save_graph()

    restored = KnowledgeGraphStore(persist_dir=tmp_path)

    assert restored.graph.nodes[paper]["year"] == 2024
    assert restored.graph.has_edge(paper, method, key="uses")


def test_entity_resolution_deduplicates_formatting_and_close_aliases(tmp_path):
    store = KnowledgeGraphStore(persist_dir=tmp_path)
    canonical = store.add_entity("GraphRAG", "Method")

    assert store.add_entity("graph rag", "Method") == canonical
    assert store.add_entity("Graph-RAG", "Method") == canonical
    assert store.graph.number_of_nodes() == 1


def test_multi_hop_retrieval_includes_incoming_and_outgoing_nodes(tmp_path):
    store = KnowledgeGraphStore(persist_dir=tmp_path)
    store.add_relation("paper-a", "method-x", "uses")
    store.add_relation("paper-b", "paper-a", "cites")

    result = store.get_multi_hop_retrieval("method-x", max_depth=2)

    assert {node["id"] for node in result["nodes"]} == {
        "paper-a",
        "paper-b",
        "method-x",
    }


def test_landscape_evolution_is_cumulative(tmp_path):
    store = KnowledgeGraphStore(persist_dir=tmp_path)
    store.add_entity("old-paper", "Paper", {"year": 2020})
    store.add_entity("new-paper", "Paper", {"year": 2022})
    store.add_relation("new-paper", "old-paper", "cites", {"year": 2022})

    evolution = store.get_landscape_evolution()

    assert [frame["year"] for frame in evolution] == [2020, 2022]
    assert evolution[-1]["cumulative_node_count"] == 2
    assert evolution[-1]["edges"][0]["type"] == "cites"


def test_sigma_export_has_stable_shape(tmp_path):
    store = KnowledgeGraphStore(persist_dir=tmp_path)
    store.add_relation("paper", "method", "uses")

    exported = store.export_for_explorer("sigmajs")

    assert len(exported["nodes"]) == 2
    assert exported["edges"][0]["source"] == "paper"
