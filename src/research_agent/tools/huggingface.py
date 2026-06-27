from __future__ import annotations

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit


class HuggingFaceDatasetAdapter(BaseToolAdapter):
    provider_name = "huggingface"
    base_url = "https://huggingface.co/api/datasets"

    def search(self, query: str, limit: int = 5) -> ToolResult:
        n = safe_limit(limit)
        items: list[dict] = []
        warnings: list[str] = []

        try:
            response = httpx.get(
                self.base_url,
                params={"search": query, "sort": "downloads", "direction": "-1", "limit": n},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                warnings.append("Unexpected HuggingFace API response format")
                return ToolResult(provider=self.provider_name, items=items, warnings=warnings)
            for ds in data[:n]:
                items.append({
                    "name": ds.get("id", ""),
                    "description": (ds.get("cardData") or {}).get("description", ""),
                    "downloads": ds.get("downloads", 0),
                    "likes": ds.get("likes", 0),
                    "tags": ds.get("tags", []),
                    "url": f"https://huggingface.co/datasets/{ds.get('id', '')}",
                })
        except httpx.HTTPError as e:
            warnings.append(f"HuggingFace API error: {e}")
        except Exception as e:
            warnings.append(f"HuggingFace error: {e}")

        return ToolResult(provider=self.provider_name, items=items, warnings=warnings)
