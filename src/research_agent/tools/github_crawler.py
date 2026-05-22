from __future__ import annotations

import os
import aiohttp
from typing import Optional

from research_agent.tools.base import BaseToolAdapter, ToolResult

class GitHubCrawlerAdapter(BaseToolAdapter):
    """Searches for and summarizes GitHub repositories related to research topics."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GITHUB_TOKEN")
        self.provider_name = "github"

    async def asearch(self, query: str, limit: int = 5) -> ToolResult:
        headers = {
            "Accept": "application/vnd.github.v3+json",
        }
        if self.api_key:
            headers["Authorization"] = f"token {self.api_key}"

        # Search for repositories
        # We append 'code' or 'implementation' to find more relevant results if not present
        search_query = query
        if "github" not in query.lower() and "code" not in query.lower():
             search_query = f"{query} implementation"

        url = f"https://api.github.com/search/repositories?q={search_query}&per_page={limit}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return ToolResult(
                            provider=self.provider_name,
                            items=[],
                            warnings=[f"GitHub API returned status {resp.status}"]
                        )
                    
                    data = await resp.json()
                    items = []
                    for repo in data.get("items", []):
                        items.append({
                            "title": repo.get("full_name"),
                            "url": repo.get("html_url"),
                            "snippet": repo.get("description"),
                            "stars": repo.get("stargazers_count"),
                            "language": repo.get("language"),
                            "updated_at": repo.get("updated_at"),
                            "year": repo.get("updated_at", "")[:4] if repo.get("updated_at") else None,
                        })
                    
                    return ToolResult(
                        provider=self.provider_name,
                        items=items
                    )
        except Exception as e:
            return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=[f"GitHub search failed: {str(e)}"]
            )

    def search(self, query: str, limit: int = 5) -> ToolResult:
        # Simple sync wrapper or implementation
        import asyncio
        return asyncio.run(self.asearch(query, limit))
