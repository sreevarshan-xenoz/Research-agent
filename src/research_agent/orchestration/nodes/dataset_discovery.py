from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from research_agent.models import agenerate_json
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState
from research_agent.tools.huggingface import HuggingFaceDatasetAdapter
from research_agent.tools.kaggle import KaggleDatasetAdapter

logger = logging.getLogger(__name__)


async def dataset_discovery_node(state: GraphState) -> dict:
    """Extracts keyword search terms from topic, searches HuggingFace and Kaggle APIs
    for relevant datasets, ranks them by popularity, and exports them to discovered_datasets.json.
    """
    await apublish_progress(
        agent="Dataset Finder",
        status="running",
        detail="Extracting search terms",
        message="Identifying relevant datasets",
    )

    topic = state.get("topic", "")
    run_id = state["run_id"]
    artifact_root = state.get("artifact_root", ".runtime/artifacts")
    run_dir = Path(artifact_root) / run_id

    if not topic:
        await apublish_progress(
            agent="Dataset Finder",
            status="complete",
            detail="No topic specified",
            message="Discovery skipped",
        )
        return {"phase": "completed"}

    prompt = (
        f"Extract 2 to 3 short, relevant keyword search terms (1-3 words each) that would be suitable for searching datasets on Hugging Face or Kaggle related to the following research topic.\n\n"
        f"Topic: {topic}\n\n"
        f"Return the search terms in a JSON object with a key 'keywords' containing a list of strings."
    )

    keywords = [topic]
    try:
        res = await agenerate_json(
            role="orchestrator",
            prompt=prompt,
            temperature=0.0
        )
        if isinstance(res, dict) and "keywords" in res:
            keywords = res["keywords"]
    except Exception as e:
        logger.warning(f"LLM keyword extraction failed: {e}. Falling back to topic query.")

    await apublish_progress(
        agent="Dataset Finder",
        status="running",
        detail="Searching repositories",
        message="Searching HuggingFace & Kaggle",
    )

    hf = HuggingFaceDatasetAdapter()
    kaggle = KaggleDatasetAdapter()

    all_datasets = []
    seen_urls = set()

    for kw in keywords[:3]:
        try:
            hf_res = hf.search(kw, limit=5)
            if hf_res and hf_res.items:
                for item in hf_res.items:
                    url = item.get("url")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_datasets.append({
                            "name": item.get("name") or kw,
                            "description": item.get("description") or "",
                            "downloads": int(item.get("downloads") or 0),
                            "likes": int(item.get("likes") or 0),
                            "url": url,
                            "provider": "huggingface"
                        })
        except Exception as e:
            logger.error(f"HuggingFace dataset query failed for '{kw}': {e}")

        try:
            kaggle_res = kaggle.search(kw, limit=5)
            if kaggle_res and kaggle_res.items:
                for item in kaggle_res.items:
                    url = item.get("url")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_datasets.append({
                            "name": item.get("name") or kw,
                            "description": item.get("description") or "",
                            "downloads": int(item.get("downloads") or 0),
                            "url": url,
                            "provider": "kaggle"
                        })
        except Exception as e:
            logger.error(f"Kaggle dataset query failed for '{kw}': {e}")

    all_datasets.sort(key=lambda x: x.get("downloads", 0), reverse=True)
    top_datasets = all_datasets[:10]

    run_dir.mkdir(parents=True, exist_ok=True)
    datasets_file = run_dir / "discovered_datasets.json"
    try:
        datasets_file.write_text(json.dumps({"datasets": top_datasets}, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to write discovered_datasets.json: {e}")

    await apublish_progress(
        agent="Dataset Finder",
        status="complete",
        detail=f"Found {len(top_datasets)} datasets",
        message="Discovery complete",
    )

    return {"phase": "completed"}
