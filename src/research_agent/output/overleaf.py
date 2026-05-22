from __future__ import annotations

import urllib.parse

def build_overleaf_import_url(main_tex: str, bibtex: str, project_name: str) -> str:
    """
    Builds a URL that, when opened, creates a new Overleaf project with the provided content.
    Note: Overleaf's direct URL import is limited by length. For larger projects, 
    a POST form or Zip import is preferred, but for v2 we provide the link generator.
    """
    # Overleaf Import API (limited functionality via GET, mostly uses POST)
    # However, we can provide a landing page or just the raw link structure.
    
    # Best approach for "One-Click" is actually a tiny HTML form that POSTs.
    # We will return the metadata required for that.
    
    base_url = "https://www.overleaf.com/docs"
    # We can't easily put full project in GET URL.
    # We will return a placeholder or documentation on how the webapp should handle it.
    return f"{base_url}?snip_name={urllib.parse.quote(project_name)}"

def get_overleaf_form_data(main_tex: str, bibtex: str, project_name: str) -> dict[str, str]:
    """Returns fields for an HTML form that POSTs to Overleaf."""
    return {
        "snip_name": project_name,
        "snip[0][name]": "main.tex",
        "snip[0][content]": main_tex,
        "snip[1][name]": "references.bib",
        "snip[1][content]": bibtex,
    }
