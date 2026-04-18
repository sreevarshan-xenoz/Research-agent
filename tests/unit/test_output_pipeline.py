from __future__ import annotations

from pathlib import Path

from research_agent.output import export_run_artifacts
from research_agent.output.latex import build_bibtex, render_main_tex, validate_latex_package


def test_render_main_tex_for_ieee_template() -> None:
    tex = render_main_tex(
        template_name="ieee",
        title="Test Title",
        author_block="Test Author",
        abstract="Short abstract.",
        body="\\section{Intro}\\nBody text.",
    )
    assert "\\documentclass[conference]{IEEEtran}" in tex
    assert "Test Title" in tex
    assert "\\section{Intro}" in tex


def test_build_bibtex_generates_entries() -> None:
    bib = build_bibtex(
        [
            {
                "key": "ref1",
                "title": "Paper One",
                "author": "A. Author",
                "year": "2025",
                "url": "https://example.com",
            }
        ]
    )
    assert "@misc{ref1" in bib
    assert "Paper One" in bib


def test_export_run_artifacts_writes_files(tmp_path: Path) -> None:
    run_dir = export_run_artifacts(
        artifact_root=str(tmp_path),
        run_id="run-test",
        main_tex="\\documentclass{article}\\begin{document}x\\end{document}",
        bibtex="@misc{x,title={t},author={a},year={2026}}",
        summary={"ok": True},
        template_name="ieee",
    )
    exported = Path(run_dir)
    assert (exported / "main.tex").exists()
    assert (exported / "references.bib").exists()
    assert (exported / "compile_instructions.md").exists()
    assert (exported / "summary.json").exists()


def test_validate_latex_package_accepts_valid_ieee_package() -> None:
    main_tex = (
        "\\documentclass[conference]{IEEEtran}\n"
        "\\begin{document}\n"
        "\\title{A}\n"
        "\\author{B}\n"
        "\\begin{abstract}X\\end{abstract}\n"
        "\\section{Intro}\n"
        "Text \\cite{ref1}.\n"
        "\\bibliography{references}\n"
        "\\end{document}\n"
    )
    bibtex = "@misc{ref1,title={t},author={a},year={2026}}"

    errors = validate_latex_package(template_name="ieee", main_tex=main_tex, bibtex=bibtex)
    assert errors == []


def test_validate_latex_package_flags_unresolved_citations() -> None:
    main_tex = (
        "\\documentclass[sigconf]{acmart}\n"
        "\\begin{document}\n"
        "\\title{A}\n"
        "\\author{B}\n"
        "\\begin{abstract}X\\end{abstract}\n"
        "\\section{Intro}\n"
        "Text \\cite{missing_key}.\n"
        "\\bibliography{references}\n"
        "\\end{document}\n"
    )

    errors = validate_latex_package(template_name="acm", main_tex=main_tex, bibtex="")
    assert any(err.startswith("unresolved_citations:") for err in errors)
