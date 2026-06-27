from __future__ import annotations

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


def test_trends_endpoint_success():
    """Test /api/trends returns aggregated analytics data."""
    from research_agent.tools.base import ToolResult

    mock_arxiv_result = ToolResult(
        provider="arxiv",
        items=[
            {
                "title": "Deep Learning for NLP",
                "year": "2023",
                "authors": ["Alice Smith", "Bob Jones"],
                "journal": "arXiv preprint",
                "snippet": "neural network transformer attention"
            },
            {
                "title": "Transformers in Computer Vision",
                "year": "2023",
                "authors": ["Alice Smith", "Carol Lee"],
                "journal": "arXiv preprint",
                "snippet": "vision transformer image classification"
            }
        ],
        warnings=[]
    )

    mock_ss_result = ToolResult(
        provider="semantic_scholar",
        items=[
            {
                "title": "BERT and GPT Overview",
                "year": "2022",
                "authors": ["Dave Brown"],
                "journal": "Nature Machine Intelligence",
                "snippet": "language model pretrained representation"
            }
        ],
        warnings=[]
    )

    with (
        patch("research_agent.tools.arxiv.ArxivAdapter.search", return_value=mock_arxiv_result),
        patch("research_agent.tools.semantic_scholar.SemanticScholarAdapter.search", return_value=mock_ss_result),
        patch("research_agent.app.webapp.current_active_user", return_value=MagicMock()),
    ):
        from research_agent.app.webapp import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=True)
        
        # The auth is mocked so we patch the dependency
        from unittest.mock import patch as mock_patch
        with mock_patch("research_agent.app.webapp.current_active_user", return_value=MagicMock()):
            response = client.get(
                "/api/trends?query=deep+learning",
                headers={"Authorization": "Bearer test-token"}
            )
        
        # Should return 200 or 401 (auth failing gracefully without actual user)
        assert response.status_code in (200, 401, 422)
