import uuid

from fastapi.testclient import TestClient

from research_agent.app.auth import User, current_active_user
from research_agent.app.webapp import create_app as _create_app


def create_app(*args, **kwargs):
    app = _create_app(*args, **kwargs)
    async def mock_current_active_user() -> User:
        return User(
            id=uuid.UUID("12345678-1234-5678-1234-567812345678"),
            email="test@example.com",
            hashed_password="...",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
    app.dependency_overrides[current_active_user] = mock_current_active_user
    return app


def test_render_status_endpoint(tmp_path):
    run_id = "test-run-002"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "main.tex").write_text(r"\documentclass{article}\begin{document}Hello\end{document}")
    app = create_app(artifact_root=str(tmp_path))
    client = TestClient(app)
    resp = client.get(f"/api/runs/{run_id}/render/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "cached" in data
    assert "tectonic_available" in data
