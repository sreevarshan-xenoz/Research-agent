from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

def aggregate_team_analytics() -> dict[str, Any]:
    """Aggregates cost and usage metrics from all completed runs in the artifacts folder."""
    artifact_root = Path(os.getenv("ARTIFACT_ROOT", ".runtime/artifacts"))
    if not artifact_root.exists():
        return {"total_runs": 0, "total_cost_usd": 0.0}

    total_cost = 0.0
    total_runs = 0
    provider_counts: dict[str, int] = {}
    topic_clusters: List[str] = []

    for run_dir in artifact_root.iterdir():
        if not run_dir.is_dir():
            continue
        
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                total_runs += 1
                total_cost += float(summary.get("total_cost_usd", 0.0))
                topic_clusters.append(summary.get("topic", "unknown"))
                
                # Check metrics if available
                metrics = summary.get("metrics", {})
                for prov in metrics.keys():
                    provider_counts[prov] = provider_counts.get(prov, 0) + 1
            except Exception:
                continue

    analytics = {
        "total_runs": total_runs,
        "total_cost_usd": round(total_cost, 4),
        "provider_popularity": provider_counts,
        "recent_topics": topic_clusters[-10:] # Last 10
    }
    
    analytics_file = artifact_root.parent / "team_analytics.json"
    analytics_file.write_text(json.dumps(analytics, indent=2, ensure_ascii=True), encoding="utf-8")
    return analytics
