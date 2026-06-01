from __future__ import annotations

import os

import httpx

from research_agent.tools.base import BaseToolAdapter, ToolResult, safe_limit


class KaggleDatasetAdapter(BaseToolAdapter):
    provider_name = "kaggle"

    def search(self, query: str, limit: int = 5) -> ToolResult:
        n = safe_limit(limit)
        items: list[dict] = []
        warnings: list[str] = []

        api_key = os.getenv("KAGGLE_API_KEY", "")
        if not api_key:
            warnings.append("KAGGLE_API_KEY not set, skipping Kaggle")
            return ToolResult(provider=self.provider_name, items=items, warnings=warnings)

        try:
            headers = {"Authorization": f"Bearer {api_key}"}
            response = httpx.get(
                "https://www.kaggle.com/api/v1/datasets/list",
                params={"search": query, "sortBy": "hottest", "page": 1, "max": n},
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                for ds in data[:n]:
                    items.append({
                        "name": ds.get("title", ""),
                        "description": ds.get("subtitle", "") or ds.get("description", ""),
                        "size": ds.get("datasetSize", ""),
                        "downloads": ds.get("totalDownloads", 0),
                        "url": f"https://kaggle.com/datasets/{ds.get('ref', '')}",
                        "provider": "kaggle",
                    })
            else:
                warnings.append(f"Kaggle API returned {response.status_code}")
        except httpx.HTTPError as e:
            warnings.append(f"Kaggle API error: {e}")
        except Exception as e:
            warnings.append(f"Kaggle error: {e}")

        return ToolResult(provider=self.provider_name, items=items, warnings=warnings)
