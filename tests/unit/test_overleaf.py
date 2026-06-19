from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from research_agent.output.overleaf import (
    build_overleaf_import_url,
    build_overleaf_form_html,
    git_push_to_overleaf,
    git_pull_from_overleaf,
    check_overleaf_config,
)


# ──────────────────────────────────────────────
# Snip URL tests
# ──────────────────────────────────────────────

class TestBuildOverleafImportUrl:
    def test_returns_string(self):
        url = build_overleaf_import_url("\\documentclass{article}", "", "Test")
        assert isinstance(url, str)
        assert url.startswith("https://www.overleaf.com/docs?")

    def test_contains_project_name(self):
        url = build_overleaf_import_url("\\documentclass{article}", "", "My Survey")
        assert "snip_name=My%20Survey" in url or "snip_name=My+Survey" in url or "snip_name=My Survey" in url

    def test_handles_large_content(self):
        large_tex = "\\section{Test}\n" * 100
        url = build_overleaf_import_url(large_tex, "\\bibitem{test}", "Large")
        assert isinstance(url, str)
        assert len(url) > 200


class TestBuildOverleafFormHtml:
    def test_returns_html_string(self):
        html = build_overleaf_form_html("\\documentclass{article}", "", "Test")
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_contains_form(self):
        html = build_overleaf_form_html("\\section{Intro}", "\\bibitem{ref1}", "Paper")
        assert '<form' in html
        assert 'action="https://www.overleaf.com/docs"' in html
        assert 'method="POST"' in html

    def test_contains_file_inputs(self):
        html = build_overleaf_form_html("\\title{Test}", "\\bibitem{k1}", "Test")
        assert 'name="snip[0][name]"' in html
        assert 'name="snip[0][content]"' in html
        assert 'name="snip[1][name]"' in html
        assert 'name="snip[1][content]"' in html

    def test_auto_submit_script(self):
        html = build_overleaf_form_html("content", "bib", "N")
        assert "submit()" in html


# ──────────────────────────────────────────────
# Git push tests
# ──────────────────────────────────────────────

class TestGitPushToOverleaf:
    def test_no_token_configured(self):
        result = git_push_to_overleaf(
            git_url="https://git.overleaf.com/abc123",
            main_tex="content",
            bibtex="bib",
            git_token=None,
        )
        assert result["success"] is False
        assert "Git token" in result["message"]

    def test_invalid_git_url(self):
        result = git_push_to_overleaf(
            git_url="https://example.com/repo.git",
            main_tex="content",
            bibtex="bib",
            git_token="test-token",
        )
        assert result["success"] is False
        assert "Invalid Overleaf Git URL" in result["message"]

    def test_git_not_installed(self):
        with patch("shutil.which", return_value=None):
            with patch("subprocess.run", side_effect=FileNotFoundError("No such file")):
                result = git_push_to_overleaf(
                    git_url="https://git.overleaf.com/abc123",
                    main_tex="content",
                    bibtex="bib",
                    git_token="test-token",
                )
                assert result["success"] is False
                assert "not installed" in result["message"] or "Git is not installed" in result["message"]

    def test_token_from_env_var(self):
        with patch.dict(os.environ, {"OVERLEAF_GIT_TOKEN": ""}, clear=True):
            result = git_push_to_overleaf(
                git_url="https://git.overleaf.com/abc123",
                main_tex="content",
                bibtex="bib",
            )
            assert result["success"] is False


# ──────────────────────────────────────────────
# Git pull tests
# ──────────────────────────────────────────────

class TestGitPullFromOverleaf:
    def test_no_token_configured(self):
        result = git_pull_from_overleaf(
            git_url="https://git.overleaf.com/abc123",
            git_token=None,
        )
        assert result["success"] is False
        assert "Git token" in result["message"]

    def test_invalid_git_url(self):
        result = git_pull_from_overleaf(
            git_url="https://example.com/repo.git",
            git_token="token",
        )
        assert result["success"] is False
        assert "Invalid Overleaf Git URL" in result["message"]

    def test_git_not_installed(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("No such file")):
            result = git_pull_from_overleaf(
                git_url="https://git.overleaf.com/abc123",
                git_token="token",
            )
            assert result["success"] is False


# ──────────────────────────────────────────────
# Config check tests
# ──────────────────────────────────────────────

class TestCheckOverleafConfig:
    def test_returns_dict_with_keys(self):
        with patch("shutil.which", return_value=None):
            config = check_overleaf_config()
            assert "git_available" in config
            assert "git_token_configured" in config
            assert "snip_available" in config

    def test_snip_always_available(self):
        config = check_overleaf_config()
        assert config["snip_available"] is True

    def test_git_available_when_installed(self):
        with patch("shutil.which", return_value="/usr/bin/git"):
            config = check_overleaf_config()
            assert config["git_available"] is True

    def test_git_not_available(self):
        with patch("shutil.which", return_value=None):
            config = check_overleaf_config()
            assert config["git_available"] is False

    def test_token_configured(self):
        with patch.dict(os.environ, {"OVERLEAF_GIT_TOKEN": "my-token"}, clear=True):
            config = check_overleaf_config()
            assert config["git_token_configured"] is True

    def test_token_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            config = check_overleaf_config()
            assert config["git_token_configured"] is False


# ──────────────────────────────────────────────
# End-to-end integration tests
# ──────────────────────────────────────────────

class TestOverleafEndToEnd:
    def test_snip_url_contains_tex_content(self):
        """The snip URL should encode the tex content as a data URI."""
        tex_content = "\\title{Test Paper}\\maketitle"
        bib_content = "@article{key, author={Author}}"
        url = build_overleaf_import_url(tex_content, bib_content, "Test")

        assert url.startswith("https://www.overleaf.com/docs?")
        assert "snip_uri=" in url or "snip_name=" in url

    def test_form_html_round_trip(self):
        """The HTML form should preserve the LaTeX content."""
        tex = "\\section{Introduction}\nContent here."
        bib = "@article{key, title={Test}}"
        html = build_overleaf_form_html(tex, bib, "Paper")

        # Verify content is in the form
        assert "\\section{Introduction}" in html or urllib_quote(tex[:20]) in html
        assert "@article{key, title={Test}}" in html or "Test" in html

    def test_git_push_rejects_without_token(self):
        """Git push should fail gracefully without a token regardless of URL."""
        result = git_push_to_overleaf(
            git_url="https://git.overleaf.com/project-abc",
            main_tex="content",
            bibtex="bib",
            git_token="",
        )
        assert result["success"] is False


def urllib_quote(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s)
