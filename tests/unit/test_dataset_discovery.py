import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import json

from research_agent.orchestration.nodes.dataset_discovery import dataset_discovery_node
from research_agent.tools.base import ToolResult


@pytest.mark.asyncio
async def test_dataset_discovery_no_topic():
    state = {
        "run_id": "test_run",
        "topic": "",
        "artifact_root": ".runtime/artifacts"
    }
    result = await dataset_discovery_node(state)
    assert result["phase"] == "completed"


@pytest.mark.asyncio
async def test_dataset_discovery_success(tmp_path):
    mock_keywords = {"keywords": ["machine learning", "deep learning"]}
    mock_hf_result = ToolResult(
        provider="huggingface",
        items=[
            {"name": "ds-ml-1", "description": "desc 1", "downloads": 100, "likes": 10, "url": "https://huggingface.co/datasets/ds-ml-1"},
        ],
        warnings=[]
    )
    mock_kaggle_result = ToolResult(
        provider="kaggle",
        items=[
            {"name": "ds-kaggle-1", "description": "desc 2", "downloads": 200, "url": "https://kaggle.com/datasets/ds-kaggle-1"},
        ],
        warnings=[]
    )

    state = {
        "run_id": "test_run_discovery",
        "topic": "Machine Learning in Software Engineering",
        "artifact_root": str(tmp_path)
    }

    with (
        patch("research_agent.orchestration.nodes.dataset_discovery.agenerate_json", new=AsyncMock(return_value=mock_keywords)),
        patch("research_agent.tools.huggingface.HuggingFaceDatasetAdapter.search", return_value=mock_hf_result),
        patch("research_agent.tools.kaggle.KaggleDatasetAdapter.search", return_value=mock_kaggle_result),
    ):
        result = await dataset_discovery_node(state)
        assert result["phase"] == "completed"

        datasets_file = tmp_path / "test_run_discovery" / "discovered_datasets.json"
        assert datasets_file.exists()
        
        data = json.loads(datasets_file.read_text(encoding="utf-8"))
        assert "datasets" in data
        assert len(data["datasets"]) == 2
        assert data["datasets"][0]["downloads"] == 200
        assert data["datasets"][1]["downloads"] == 100
        assert data["datasets"][0]["provider"] == "kaggle"
        assert data["datasets"][1]["provider"] == "huggingface"
