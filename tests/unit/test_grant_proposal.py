import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import json

from research_agent.orchestration.nodes.grant_proposal import grant_proposal_node


@pytest.mark.asyncio
async def test_grant_proposal_success(tmp_path):
    mock_proposal = "# NSF Proposal Draft\nThis is a mock proposal draft."

    state = {
        "run_id": "test_run_proposal",
        "topic": "Machine Learning in Software Engineering",
        "peer_review_report": "Good math verification.",
        "math_verification_report": "All tests passed.",
        "artifact_root": str(tmp_path)
    }

    with patch("research_agent.orchestration.nodes.grant_proposal.agenerate_text", new=AsyncMock(return_value=mock_proposal)):
        result = await grant_proposal_node(state)
        # Should return empty dict on completion
        assert result == {}

        proposal_file = tmp_path / "test_run_proposal" / "grant_proposal.md"
        assert proposal_file.exists()
        
        content = proposal_file.read_text(encoding="utf-8")
        assert content == mock_proposal
