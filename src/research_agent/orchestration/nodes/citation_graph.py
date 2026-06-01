from __future__ import annotations

from typing import Any


class CitationGraph:
    def build(self, papers: list[dict[str, Any]]) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for paper in papers:
            node_id = str(paper.get("id", paper.get("title", "")))
            if node_id and node_id not in seen_ids:
                seen_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "label": paper.get("title", "Untitled"),
                    "authors": paper.get("authors", "Unknown"),
                    "year": paper.get("year", 0),
                    "group": 1,
                    "url": paper.get("url", ""),
                })

            citations = paper.get("citations", paper.get("references", []))
            if isinstance(citations, list):
                for ref in citations:
                    ref_id = None
                    if isinstance(ref, str):
                        ref_id = ref
                    elif isinstance(ref, dict):
                        ref_id = str(ref.get("id", ref.get("title", "")))
                    
                    if ref_id and ref_id not in seen_ids:
                        seen_ids.add(ref_id)
                        nodes.append({
                            "id": ref_id,
                            "label": ref if isinstance(ref, str) else ref.get("title", ref_id),
                            "authors": "",
                            "year": 0,
                            "group": 2,
                            "url": "",
                        })
                    
                    if ref_id:
                        edges.append({
                            "source": ref_id,
                            "target": node_id,
                            "type": "cites",
                        })

        return {"nodes": nodes, "edges": edges}


def citation_graph_node(state: dict[str, Any]) -> dict[str, Any]:
    findings = state.get("task_findings", {})
    papers = []
    for task_id, task_data in findings.items():
        if isinstance(task_data, dict):
            for provider, provider_data in task_data.items():
                if isinstance(provider_data, dict):
                    for item in provider_data.get("items", []):
                        if isinstance(item, dict):
                            papers.append(item)

    graph = CitationGraph()
    data = graph.build(papers)
    return {"citation_graph_data": data}
