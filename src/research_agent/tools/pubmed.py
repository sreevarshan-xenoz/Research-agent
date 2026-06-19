from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit, retry_with_backoff_sync


class PubMedAdapter(BaseToolAdapter):
    """Adapter for NCBI PubMed (NIH) - covering life sciences and biomedical literature."""
    provider_name = "pubmed"

    def __init__(
        self,
        *,
        base_url: str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url
        self._client = client or httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "ResearchAgent/0.1 (research-agent; mailto:noreply@example.com)",
            },
        )

    def search(self, query: str, limit: int = 5) -> ToolResult:
        normalized_limit = safe_limit(limit)

        def _do_search_ids() -> list[str]:
            search_params: dict[str, Any] = {
                "db": "pubmed",
                "term": query,
                "retmax": normalized_limit,
                "usehistory": "n",
            }
            search_resp = self._client.get(f"{self._base_url}/esearch.fcgi", params=search_params)
            search_resp.raise_for_status()
            root = ET.fromstring(search_resp.text)
            return [
                id_elem.text for id_list_elem in root.findall("IdList")
                for id_elem in id_list_elem.findall("Id")
                if id_elem.text is not None
            ]

        try:
            id_list = retry_with_backoff_sync(_do_search_ids, "pubmed")

            if not id_list:
                return ToolResult(
                    provider=self.provider_name,
                    items=[],
                    metadata={"query": query, "limit": normalized_limit, "raw_count": 0}
                )

            def _do_fetch_summary() -> dict[str, Any]:
                summary_params: dict[str, Any] = {
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "json",
                }
                summary_resp = self._client.get(f"{self._base_url}/esummary.fcgi", params=summary_params)
                summary_resp.raise_for_status()
                return summary_resp.json()

            summary_data = retry_with_backoff_sync(_do_fetch_summary, "pubmed")
            results = summary_data.get("result", {})
            uids = results.get("uids", [])

            items = []
            for uid in uids:
                item_raw = results.get(uid, {})
                items.append(self._normalize_item(uid, item_raw))

            return ToolResult(
                provider=self.provider_name,
                items=items,
                metadata={"query": query, "limit": normalized_limit, "raw_count": len(items)},
            )

        except Exception as exc:
            return ToolResult(
                provider=self.provider_name,
                warnings=[f"pubmed_error:{type(exc).__name__}"],
                metadata={"query": query, "limit": normalized_limit},
            )

    @staticmethod
    def _normalize_item(uid: str, row: dict[str, Any]) -> dict[str, Any]:
        """Normalize a PubMed summary result into our common format."""
        title = row.get("title", "")
        # Clean title residue (often in square brackets or ending with period)
        title = title.strip(". ")
        
        authors = [a.get("name", "") for a in row.get("authors", [])]
        year = row.get("pubdate", "").split(" ")[0] if row.get("pubdate") else ""
        
        # Build URL
        doi = ""
        article_ids = row.get("articleids", [])
        for aid in article_ids:
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
                break
        
        url = f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{uid}/"

        journal = row.get("fulljournalname") or ""
        volume = row.get("volume") or ""
        number = row.get("issue") or ""
        pages = row.get("pages") or ""
        publisher = row.get("publisher") or ""
        pubtypes = row.get("pubtype") or []
        doc_type = pubtypes[0] if pubtypes else "Journal Article"

        return {
            "title": title,
            "url": url,
            "snippet": f"PubMed ID: {uid}. Source: {row.get('fulljournalname', 'PubMed')}",
            "paper_id": uid,
            "year": year,
            "authors": authors,
            "source_type": "paper",
            "provider": "pubmed",
            "journal": journal,
            "booktitle": "",
            "volume": str(volume),
            "number": str(number),
            "pages": pages,
            "doi": doi,
            "publisher": publisher,
            "type": doc_type,
        }
