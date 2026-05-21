from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any
import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit


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
        
        try:
            # Step 1: Search for IDs
            search_params: dict[str, Any] = {
                "db": "pubmed",
                "term": query,
                "retmax": normalized_limit,
                "usehistory": "n",
            }
            search_resp = self._client.get(f"{self._base_url}/esearch.fcgi", params=search_params)
            search_resp.raise_for_status()
            
            # Simple XML parsing for IDs
            root = ET.fromstring(search_resp.text)
            id_list = [id_elem.text for id_list_elem in root.findall("IdList") for id_elem in id_list_elem.findall("Id") if id_elem.text is not None]
            
            if not id_list:
                return ToolResult(
                    provider=self.provider_name,
                    items=[],
                    metadata={"query": query, "limit": normalized_limit, "raw_count": 0}
                )

            # Step 2: Fetch metadata for those IDs
            summary_params: dict[str, Any] = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
            }
            summary_resp = self._client.get(f"{self._base_url}/esummary.fcgi", params=summary_params)
            summary_resp.raise_for_status()
            summary_data = summary_resp.json()
            
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

        except Exception as exc:  # noqa: BLE001
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

        return {
            "title": title,
            "url": url,
            "snippet": f"PubMed ID: {uid}. Source: {row.get('fulljournalname', 'PubMed')}",
            "paper_id": uid,
            "year": year,
            "authors": authors,
            "source_type": "paper",
            "provider": "pubmed",
        }
