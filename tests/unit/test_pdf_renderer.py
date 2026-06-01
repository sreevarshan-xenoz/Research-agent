from research_agent.output.pdf_renderer import compile_pdf, get_pdf_path

def test_get_pdf_path_uncached(tmp_path):
    run_dir = tmp_path / "test-run"
    run_dir.mkdir()
    (run_dir / "main.tex").write_text(r"\documentclass{article}\begin{document}Hello\end{document}")
    assert get_pdf_path(run_dir) is None

def test_compile_pdf_no_tectonic(tmp_path, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda x: None)
    run_dir = tmp_path / "test-run"
    run_dir.mkdir()
    (run_dir / "main.tex").write_text(r"\documentclass{article}\begin{document}Hello\end{document}")
    pdf = compile_pdf(run_dir)
    assert pdf is None
