"""
P27: Multi-Format Submission Pipeline — API Routes

API endpoints for:
- Format conversion (IEEE ↔ ACM ↔ Springer ↔ Elsevier)
- Style compliance checking
- Content adaptation
- One-click export (Overleaf, arXiv ZIP, conference ZIP)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from research_agent.app.auth import User, current_active_user
from research_agent.output.submission_pipeline import (
    run_submission_pipeline,
    create_export_zip,
)
from research_agent.output.format_converter import (
    convert_latex_format,
    convert_to_all_formats,
    list_formats,
)
from research_agent.output.style_checker import check_style
from research_agent.output.content_adapter import adapt_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/submission", tags=["submission"])


# ── Request Models ───────────────────────────────────────────

class FormatConvertRequest(BaseModel):
    tex: str
    target_format: str
    bibtex: str | None = None
    topic: str | None = None


class StyleCheckRequest(BaseModel):
    tex: str
    format: str  # format_name
    bibtex: str | None = None


class AdaptContentRequest(BaseModel):
    tex: str
    format: str
    bibtex: str | None = None
    target_pages: int | None = None


class PipelineRequest(BaseModel):
    tex: str
    format: str = "ieee"
    bibtex: str | None = None
    topic: str | None = None
    run_id: str | None = None
    check_only: bool = False


class ExportZipRequest(BaseModel):
    files: dict[str, str]
    archive_name: str = "export.zip"


# ── Endpoints ────────────────────────────────────────────────

@router.get("/formats")
async def get_formats():
    """List all supported export formats with descriptions."""
    return {"formats": list_formats()}


@router.post("/convert")
async def convert_format(
    req: FormatConvertRequest,
    user: User = Depends(current_active_user),
):
    """Convert LaTeX between conference/journal formats."""
    if req.target_format not in ("ieee", "acm", "springer", "elsevier"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {req.target_format}. "
                   f"Supported: ieee, acm, springer, elsevier",
        )
    try:
        result = await convert_latex_format(
            req.tex, req.target_format, bibtex=req.bibtex, topic=req.topic,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}")


@router.post("/convert/all")
async def convert_all_formats(
    req: FormatConvertRequest,
    user: User = Depends(current_active_user),
):
    """Convert LaTeX to all supported formats."""
    try:
        result = await convert_to_all_formats(
            req.tex, bibtex=req.bibtex, topic=req.topic,
        )
        return {"results": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}")


@router.post("/style-check")
async def style_check(
    req: StyleCheckRequest,
    user: User = Depends(current_active_user),
):
    """Run style compliance check against conference guidelines."""
    try:
        result = check_style(req.tex, req.format, bibtex=req.bibtex)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Style check failed: {exc}")


@router.post("/adapt")
async def adapt(
    req: AdaptContentRequest,
    user: User = Depends(current_active_user),
):
    """Auto-adapt content to fit format constraints."""
    try:
        result = await adapt_content(
            req.tex, req.format, bibtex=req.bibtex, target_pages=req.target_pages,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Content adaptation failed: {exc}")


@router.post("/pipeline")
async def submission_pipeline(
    req: PipelineRequest,
    user: User = Depends(current_active_user),
):
    """Run the full submission pipeline: check → convert → adapt → export."""
    try:
        result = await run_submission_pipeline(
            req.tex,
            format_name=req.format,
            bibtex=req.bibtex,
            topic=req.topic,
            run_id=req.run_id,
            check_only=req.check_only,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")


@router.post("/export/zip")
async def export_zip(
    req: ExportZipRequest,
    user: User = Depends(current_active_user),
):
    """Generate a downloadable ZIP archive from provided files."""
    try:
        zip_bytes, filename = create_export_zip(
            req.files, archive_name=req.archive_name,
        )
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(zip_bytes)),
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ZIP export failed: {exc}")


@router.post("/export/latex")
async def export_latex(
    req: FormatConvertRequest,
    user: User = Depends(current_active_user),
):
    """Export LaTeX as a downloadable .tex file."""
    try:
        tex_content = req.tex
        if req.target_format:
            result = await convert_latex_format(
                req.tex, req.target_format, bibtex=req.bibtex, topic=req.topic,
            )
            tex_content = result.get("tex", req.tex)

        filename = f"paper-{req.target_format or 'latex'}.tex"
        return Response(
            content=tex_content,
            media_type="application/x-latex",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")


@router.post("/run/{run_id}/pipeline")
async def run_pipeline_for_run(
    run_id: str,
    req: PipelineRequest,
    user: User = Depends(current_active_user),
):
    """Run the submission pipeline for an existing run's artifacts."""
    from research_agent.config import load_settings
    settings = load_settings()
    artifact_root = settings.output.artifact_root or ".runtime/artifacts"
    run_dir = Path(artifact_root) / run_id

    tex_path = run_dir / "main.tex"
    bib_path = run_dir / "references.bib"

    if not tex_path.exists():
        raise HTTPException(status_code=404, detail="Run artifacts not found. Run research first.")

    tex = tex_path.read_text(encoding="utf-8")
    bibtex = bib_path.read_text(encoding="utf-8") if bib_path.exists() else None

    try:
        result = await run_submission_pipeline(
            tex,
            format_name=req.format or "ieee",
            bibtex=bibtex,
            topic=req.topic or run_id,
            run_id=run_id,
            check_only=req.check_only,
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}")
