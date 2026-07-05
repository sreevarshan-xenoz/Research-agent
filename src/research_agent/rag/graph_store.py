"""GraphRAG Knowledge Graph Retrieval using NetworkX."""

from __future__ import annotations

import json
import logging
import random
import re
import tempfile
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any, Dict, List, Set

import networkx as nx

logger = logging.getLogger(__name__)


class KnowledgeGraphStore:
    """Persistent entity store across runs using NetworkX serialized to JSON."""

    def __init__(self, run_id: str = "default", persist_dir: str | Path | None = None):
        self.run_id = run_id
        if persist_dir is None:
            # Default to data/graph
            self.persist_dir = Path("data/graph")
        else:
            self.persist_dir = Path(persist_dir)
            
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.graph_file = self.persist_dir / "knowledge_graph.json"
        
        self.graph = nx.MultiDiGraph()
        self._load_graph()
        
    def _load_graph(self) -> None:
        """Load the graph from disk if it exists."""
        if self.graph_file.exists():
            try:
                with open(self.graph_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.graph = nx.node_link_graph(data, edges="edges")
                    if not isinstance(self.graph, nx.MultiDiGraph):
                        self.graph = nx.MultiDiGraph(self.graph)
                logger.info("Loaded knowledge graph with %d nodes and %d edges", 
                            self.graph.number_of_nodes(), self.graph.number_of_edges())
            except Exception as exc:
                logger.error("Failed to load knowledge graph: %s", exc)
                self.graph = nx.MultiDiGraph()
                
    def save_graph(self) -> None:
        """Save the graph to disk."""
        try:
            data = nx.node_link_data(self.graph, edges="edges")
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.persist_dir, delete=False
            ) as handle:
                json.dump(data, handle, indent=2)
                temporary_path = Path(handle.name)
            temporary_path.replace(self.graph_file)
            logger.info("Saved knowledge graph with %d nodes and %d edges", 
                        self.graph.number_of_nodes(), self.graph.number_of_edges())
        except Exception as exc:
            logger.error("Failed to save knowledge graph: %s", exc)

    def add_entity(self, entity_id: str, entity_type: str, properties: Dict[str, Any] | None = None) -> str:
        """Add an entity to the graph with deduplication/resolution."""
        # Entity resolution/deduplication: normalize ID
        normalized_id = self.resolve_entity(entity_id, entity_type) or self._normalize_entity_id(entity_id)
        
        if properties is None:
            properties = {}
        else:
            properties = dict(properties)
            
        if self.graph.has_node(normalized_id):
            # Update properties
            for k, v in properties.items():
                if k not in self.graph.nodes[normalized_id]:
                    self.graph.nodes[normalized_id][k] = v
                elif isinstance(self.graph.nodes[normalized_id][k], list) and isinstance(v, list):
                    # Merge lists
                    self.graph.nodes[normalized_id][k] = list(set(self.graph.nodes[normalized_id][k] + v))
        else:
            self.graph.add_node(
                normalized_id,
                type=entity_type,
                label=properties.pop("label", entity_id.strip()),
                aliases=[entity_id.strip()],
                **properties,
            )
            
        return normalized_id
        
    def add_relation(self, source_id: str, target_id: str, relation_type: str, properties: Dict[str, Any] | None = None) -> None:
        """Add a relationship between two entities."""
        source_id = self._normalize_entity_id(source_id)
        target_id = self._normalize_entity_id(target_id)
        
        if properties is None:
            properties = {}
            
        # Ensure nodes exist
        if not self.graph.has_node(source_id):
            self.add_entity(source_id, "Unknown")
        if not self.graph.has_node(target_id):
            self.add_entity(target_id, "Unknown")
            
        self.graph.add_edge(source_id, target_id, key=relation_type, type=relation_type, **properties)
        
    def _normalize_entity_id(self, entity_id: str) -> str:
        """Normalize entity ID for deduplication."""
        value = unicodedata.normalize("NFKC", entity_id).casefold()
        return re.sub(r"[^a-z0-9]+", "-", value).strip("-")

    def resolve_entity(
        self, entity_id: str, entity_type: str | None = None, threshold: float = 0.90
    ) -> str | None:
        """Resolve an entity to an existing canonical node using aliases and similarity."""
        normalized = self._normalize_entity_id(entity_id)
        if self.graph.has_node(normalized):
            return normalized
        best_id: str | None = None
        best_score = threshold
        for node_id, data in self.graph.nodes(data=True):
            if entity_type and data.get("type") not in {entity_type, "Unknown"}:
                continue
            candidates = [str(node_id), str(data.get("label", "")), *data.get("aliases", [])]
            score = max(
                SequenceMatcher(None, normalized, self._normalize_entity_id(candidate)).ratio()
                for candidate in candidates
                if candidate
            )
            if score > best_score:
                best_id, best_score = str(node_id), score
        return best_id
        
    def get_multi_hop_retrieval(self, start_entity: str, max_depth: int = 2) -> Dict[str, Any]:
        """Multi-hop retrieval: e.g., 'What papers cite the method used in Paper X?'"""
        start_entity = self._normalize_entity_id(start_entity)
        if not self.graph.has_node(start_entity):
            return {"error": f"Entity '{start_entity}' not found in graph."}
            
        # Use BFS to find multi-hop connections
        subgraph_nodes = set([start_entity])
        current_level = set([start_entity])
        
        for _ in range(max_depth):
            next_level = set()
            for node in current_level:
                # Outgoing edges
                for neighbor in self.graph.successors(node):
                    next_level.add(neighbor)
                # Incoming edges
                for neighbor in self.graph.predecessors(node):
                    next_level.add(neighbor)
            
            subgraph_nodes.update(next_level)
            current_level = next_level
            
        subgraph = self.graph.subgraph(subgraph_nodes)
        return nx.node_link_data(subgraph, edges="edges")
        
    def get_landscape_evolution(self) -> List[Dict[str, Any]]:
        """Time-based landscape evolution: animate research trends over years."""
        # Extract nodes with 'year' property
        yearly_data: Dict[int, Dict[str, Any]] = {}
        
        for node, data in self.graph.nodes(data=True):
            year = data.get("year")
            if year:
                try:
                    year_int = int(year)
                    if year_int not in yearly_data:
                        yearly_data[year_int] = {"nodes": [], "edges": []}
                    yearly_data[year_int]["nodes"].append({"id": node, **data})
                except (ValueError, TypeError):
                    pass
                    
        # Also include edges where both source and target exist in or before that year
        # For a cumulative view
        sorted_years = sorted(yearly_data.keys())
        cumulative_nodes: Set[str] = set()
        
        evolution = []
        for year in sorted_years:
            current_nodes = [n["id"] for n in yearly_data[year]["nodes"]]
            cumulative_nodes.update(current_nodes)
            
            # Find edges between cumulative nodes
            year_edges = []
            for u, v, k, d in self.graph.edges(keys=True, data=True):
                if u in cumulative_nodes and v in cumulative_nodes:
                    # Only add if the edge itself has a year <= current year, or no year
                    edge_year = d.get("year")
                    if not edge_year or (isinstance(edge_year, (int, str)) and str(edge_year).isdigit() and int(edge_year) <= year):
                        year_edges.append({"source": u, "target": v, "type": k, **d})
                        
            evolution.append({
                "year": year,
                "new_nodes": yearly_data[year]["nodes"],
                "cumulative_node_count": len(cumulative_nodes),
                "edges": year_edges
            })
            
        return evolution

    def export_for_explorer(self, format_type: str = "threejs") -> Dict[str, Any]:
        """Export graph data for interactive explorer (three.js or Sigma.js)."""
        data = nx.node_link_data(self.graph, edges="edges")
        
        if format_type == "sigmajs":
            # Format specifically for Sigma.js
            sigma_data: Dict[str, List[Dict[str, Any]]] = {
                "nodes": [],
                "edges": []
            }
            
            for i, node in enumerate(data.get("nodes", [])):
                node_id = node.get("id", "")
                degree = self.graph.degree(node_id) if self.graph.has_node(node_id) else 0
                sigma_data["nodes"].append({
                    "id": node_id,
                    "label": node.get("title", node_id),
                    "x": random.random() * 100,
                    "y": random.random() * 100,
                    "size": 3 + degree,
                    "color": self._get_color_for_type(node.get("type", "Unknown")),
                    "attributes": node
                })
                
            for i, edge in enumerate(data.get("edges", [])):
                sigma_data["edges"].append({
                    "id": f"e{i}",
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "label": edge.get("type", ""),
                    "color": "#ccc",
                    "size": 1
                })
                
            return sigma_data
            
        # Default to standard node-link format (works well for three.js/force-graph)
        return data
        
    def _get_color_for_type(self, entity_type: str) -> str:
        colors = {
            "Paper": "#4285F4",
            "Author": "#EA4335",
            "Method": "#FBBC05",
            "Dataset": "#34A853",
            "Task": "#8F00FF",
            "Unknown": "#999999"
        }
        return colors.get(entity_type, colors["Unknown"])
