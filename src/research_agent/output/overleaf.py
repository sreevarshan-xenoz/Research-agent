from __future__ import annotations

import base64
import logging
import os
import shutil
import subprocess
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Snip URL Integration (Official)
# ──────────────────────────────────────────────

def build_overleaf_import_url(
    main_tex: str,
    bibtex: str,
    project_name: str = "Research Project",
) -> str:
    """Build a URL that opens Overleaf's project import page with pre-filled content.

    Uses Overleaf's official 'snip' mechanism to create a new project with
    the provided LaTeX source and bibliography when the user visits the URL.

    .. warning::

        URLs have browser-dependent length limits (~2000 chars reliable).
        Base64-encoded content adds ~33% overhead. If the combined encoded
        content exceeds 1500 characters, this function logs a warning and
        the URL may not work in all browsers. Use :func:`build_overleaf_form_html`
        (POST-based, no size limit) for reliable one-click import.

    Args:
        main_tex: The main.tex content.
        bibtex: The references.bib content.
        project_name: Name for the Overleaf project.

    Returns:
        A URL to Overleaf's import page with the content embedded.
    """
    base_url = "https://www.overleaf.com/docs"

    # Use data URIs for the file content (base64-encoded)
    tex_encoded = base64.b64encode(main_tex.encode("utf-8")).decode("ascii")
    bib_encoded = base64.b64encode(bibtex.encode("utf-8")).decode("ascii")

    # Build the snip_uri parameter with data URIs for each file
    tex_data_uri = f"data://text/x-tex;base64,{tex_encoded}"
    bib_data_uri = f"data://text/x-bib;base64,{bib_encoded}"

    # Combine both files into a single snip_uri
    combined = f"{tex_data_uri},{bib_data_uri}"

    params = {
        "snip_name": project_name,
        "snip_uri": combined,
    }

    url = f"{base_url}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"

    # Warn if URL exceeds reasonable length
    if len(url) > 2000:
        logger.warning(
            "Overleaf snip URL is %d chars (recommended max: 2000). "
            "Content may be too large for a URL-based import. "
            "Use build_overleaf_form_html() or Git push instead.",
            len(url),
        )

    return url


def build_overleaf_form_html(
    main_tex: str,
    bibtex: str,
    project_name: str = "Research Project",
) -> str:
    """Build an auto-submitting HTML form that creates an Overleaf project.

    This is more reliable than the URL approach for large projects since
    POST requests don't have URL length limits. The form auto-submits
    via JavaScript when loaded in a browser.

    Args:
        main_tex: The main.tex content.
        bibtex: The references.bib content.
        project_name: Name for the Overleaf project.

    Returns:
        An HTML string with an auto-submitting form.
    """
    escaped_name = urllib.parse.quote(project_name)
    escaped_tex = urllib.parse.quote(main_tex)
    escaped_bib = urllib.parse.quote(bibtex)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Opening Overleaf...</title></head>
<body>
<form id="overleafForm" action="https://www.overleaf.com/docs" method="POST" target="_blank">
  <input type="hidden" name="snip_name" value="{escaped_name}">
  <input type="hidden" name="snip[0][name]" value="main.tex">
  <input type="hidden" name="snip[0][content]" value="{escaped_tex}">
  <input type="hidden" name="snip[1][name]" value="references.bib">
  <input type="hidden" name="snip[1][content]" value="{escaped_bib}">
</form>
<script>document.getElementById('overleafForm').submit();</script>
</body>
</html>"""


# ──────────────────────────────────────────────
# Git Integration (Official)
# ──────────────────────────────────────────────

def git_push_to_overleaf(
    git_url: str,
    main_tex: str,
    bibtex: str,
    *,
    git_token: str | None = None,
    work_dir: str | Path | None = None,
    commit_message: str = "Update from Research Agent",
) -> dict[str, Any]:
    """Push LaTeX content to an Overleaf project via Git.

    Overleaf provides a Git bridge for each project. Users enable it in
    Overleaf project settings, then provide the Git URL (e.g.
    https://git.overleaf.com/<project-id>).

    The function:
    1. Creates a temporary Git clone (or uses an existing work_dir)
    2. Writes the provided main.tex and references.bib
    3. Commits and pushes to Overleaf

    Args:
        git_url: The Overleaf project Git URL (from project menu).
        main_tex: The main.tex content to push.
        bibtex: The references.bib content to push.
        git_token: Optional Overleaf Git auth token (from Account Settings).
            If not provided, uses OVERLEAF_GIT_TOKEN env var.
        work_dir: Optional existing working directory. If not provided,
            a temp directory is created and cleaned up.
        commit_message: Commit message for the push.

    Returns:
        Dict with 'success', 'message', and optionally 'work_dir'.
    """
    token = git_token or os.getenv("OVERLEAF_GIT_TOKEN", "")
    if not token:
        return {
            "success": False,
            "message": "No Overleaf Git token configured. Set OVERLEAF_GIT_TOKEN env var or pass git_token.",
        }

    if not git_url or "overleaf.com" not in git_url.lower():
        return {
            "success": False,
            "message": f"Invalid Overleaf Git URL: {git_url}. URL must contain 'overleaf.com'.",
        }

    # Build authenticated URL
    auth_git_url = git_url.replace("https://", f"https://git:{token}@")

    cleanup = False
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="overleaf_"))
        cleanup = True

    work_dir = Path(work_dir)

    try:
        # Clone if not already a git repo
        git_dir = work_dir / ".git"
        if not git_dir.exists():
            result = subprocess.run(
                ["git", "clone", auth_git_url, str(work_dir)],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                return {
                    "success": False,
                    "message": f"Git clone failed: {result.stderr.strip() or result.stdout.strip()}",
                }
            logger.info("Cloned Overleaf project to %s", work_dir)

        # Write the LaTeX files
        tex_path = work_dir / "main.tex"
        bib_path = work_dir / "references.bib"

        tex_path.write_text(main_tex, encoding="utf-8")
        bib_path.write_text(bibtex, encoding="utf-8")

        # Git add, commit, push
        subprocess.run(
            ["git", "-C", str(work_dir), "add", "main.tex", "references.bib"],
            capture_output=True, text=True, timeout=30, check=True,
        )

        # Check if there's anything to commit
        status_result = subprocess.run(
            ["git", "-C", str(work_dir), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30,
        )
        if not status_result.stdout.strip():
            return {
                "success": True,
                "message": "No changes to push. Content is up to date.",
                "work_dir": str(work_dir) if not cleanup else None,
            }

        result = subprocess.run(
            ["git", "-C", str(work_dir), "commit", "-m", commit_message],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 and "nothing to commit" not in result.stdout:
            logger.warning("Git commit had non-zero exit: %s", result.stderr.strip())

        push_result = subprocess.run(
            ["git", "-C", str(work_dir), "push", auth_git_url, "HEAD:master"],
            capture_output=True, text=True, timeout=60,
        )
        if push_result.returncode != 0:
            return {
                "success": False,
                "message": f"Git push failed: {push_result.stderr.strip() or push_result.stdout.strip()}",
                "work_dir": str(work_dir) if not cleanup else None,
            }

        return {
            "success": True,
            "message": f"Successfully pushed to Overleaf project. {commit_message}",
            "work_dir": str(work_dir) if not cleanup else None,
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Git operation timed out (60s). Check network and Overleaf project size.",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "message": "Git is not installed. Install Git to use Overleaf push/pull.",
        }
    except Exception as exc:
        logger.exception("Overleaf Git push failed")
        return {
            "success": False,
            "message": f"Overleaf push failed: {exc}",
        }
    finally:
        # Clean up temp dir if we created it
        if cleanup and work_dir.exists():
            import shutil
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass


def git_pull_from_overleaf(
    git_url: str,
    *,
    git_token: str | None = None,
    work_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Pull the latest LaTeX content from an Overleaf project via Git.

    Returns the content of main.tex and references.bib after pulling.

    Args:
        git_url: The Overleaf project Git URL.
        git_token: Optional Overleaf Git auth token.
        work_dir: Optional existing working directory.

    Returns:
        Dict with 'success', 'message', 'main_tex', 'bibtex', and 'files'.
    """
    token = git_token or os.getenv("OVERLEAF_GIT_TOKEN", "")
    if not token:
        return {
            "success": False,
            "message": "No Overleaf Git token configured.",
        }

    if not git_url or "overleaf.com" not in git_url.lower():
        return {
            "success": False,
            "message": f"Invalid Overleaf Git URL: {git_url}. URL must contain 'overleaf.com'.",
        }

    auth_git_url = git_url.replace("https://", f"https://git:{token}@")

    cleanup = False
    if work_dir is None:
        work_dir = Path(tempfile.mkdtemp(prefix="overleaf_pull_"))
        cleanup = True

    work_dir = Path(work_dir)

    try:
        git_dir = work_dir / ".git"
        if git_dir.exists():
            # Pull existing repo
            subprocess.run(
                ["git", "-C", str(work_dir), "pull", auth_git_url, "HEAD:master"],
                capture_output=True, text=True, timeout=60, check=True,
            )
        else:
            # Fresh clone
            subprocess.run(
                ["git", "clone", auth_git_url, str(work_dir)],
                capture_output=True, text=True, timeout=60, check=True,
            )

        # Read the files
        tex_path = work_dir / "main.tex"
        bib_path = work_dir / "references.bib"

        main_tex = tex_path.read_text(encoding="utf-8") if tex_path.exists() else ""
        bibtex = bib_path.read_text(encoding="utf-8") if bib_path.exists() else ""

        # List all .tex files
        tex_files = sorted(work_dir.glob("*.tex"))
        other_files = sorted(
            f for f in work_dir.glob("*")
            if f.suffix in (".bib", ".sty", ".cls", ".png", ".jpg", ".pdf")
        )

        return {
            "success": True,
            "message": f"Pulled {len(main_tex)} chars of LaTeX and {len(bibtex)} chars of BibTeX.",
            "main_tex": main_tex,
            "bibtex": bibtex,
            "files": {
                "tex": [f.name for f in tex_files],
                "other": [f.name for f in other_files],
            },
            "work_dir": str(work_dir) if not cleanup else None,
        }

    except subprocess.TimeoutExpired:
        return {"success": False, "message": "Git pull timed out (60s)."}
    except FileNotFoundError:
        return {"success": False, "message": "Git is not installed."}
    except Exception as exc:
        logger.exception("Overleaf Git pull failed")
        return {"success": False, "message": f"Overleaf pull failed: {exc}"}
    finally:
        if cleanup and work_dir.exists():
            import shutil
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass


def check_overleaf_config() -> dict[str, Any]:
    """Check if the system is configured for Overleaf integration.

    Returns:
        Dict with 'git_available', 'git_token_configured', and 'snip_available'.
    """
    git_available = shutil.which("git") is not None
    git_token = os.getenv("OVERLEAF_GIT_TOKEN", "")

    return {
        "git_available": git_available,
        "git_token_configured": bool(git_token),
        "snip_available": True,  # Snip URL always works (no auth needed)
    }
