from __future__ import annotations

import json
from typing import Any


def format_citation_json(
    graph_data: dict[str, Any],
    width: int = 1200,
    height: int = 800,
) -> str:
    formatted = {
        "width": width,
        "height": height,
        "nodes": graph_data.get("nodes", []),
        "edges": graph_data.get("edges", []),
    }
    return json.dumps(formatted, indent=2)
