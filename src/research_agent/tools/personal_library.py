from __future__ import annotations

import os
import aiohttp
from typing import Optional

from research_agent.tools.base import BaseToolAdapter, ToolResult

class PersonalLibraryAdapter(BaseToolAdapter):
    """Syncs with personal research libraries (Zotero, Mendeley) via API or local export."""
    
    def __init__(self, zotero_api_key: Optional[str] = None, zotero_user_id: Optional[str] = None):
        self.api_key = zotero_api_key or os.getenv("ZOTERO_API_KEY")
        self.user_id = zotero_user_id or os.getenv("ZOTERO_USER_ID")
        self.provider_name = "personal_library"

    async def asearch(self, query: str, limit: int = 5) -> ToolResult:
        if not self.api_key or not self.user_id:
             return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=["Zotero API key or User ID not configured. Personal library sync disabled."]
            )

        # Zotero API URL for searching a user's library
        url = f"https://api.zotero.org/users/{self.user_id}/items?q={query}&limit={limit}&itemType=-attachment"
        headers = {"Zotero-API-Key": self.api_key}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return ToolResult(
                            provider=self.provider_name,
                            items=[],
                            warnings=[f"Zotero API returned status {resp.status}"]
                        )
                    
                    data = await resp.json()
                    items = []
                    for entry in data:
                        meta = entry.get("data", {})
                        items.append({
                            "title": meta.get("title"),
                            "url": meta.get("url"),
                            "snippet": meta.get("abstractNote"),
                            "authors": ", ".join([f"{c.get('firstName')} {c.get('lastName')}" for c in meta.get("creators", [])]),
                            "year": meta.get("date", "")[:4] if meta.get("date") else None,
                            "publisher": meta.get("publicationTitle"),
                        })
                    
                    return ToolResult(
                        provider=self.provider_name,
                        items=items
                    )
        except Exception as e:
            return ToolResult(
                provider=self.provider_name,
                items=[],
                warnings=[f"Personal library sync failed: {str(e)}"]
            )

    def search(self, query: str, limit: int = 5) -> ToolResult:
        import asyncio
        return asyncio.run(self.asearch(query, limit))
