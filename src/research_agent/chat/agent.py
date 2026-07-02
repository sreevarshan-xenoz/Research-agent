"""Agentic research assistant with tool-calling loop.

Provides an intelligent agent that:
1. Takes a user query
2. Decides which tools to call (web search, paper search, dataset discovery, PDF analysis)
3. Executes tools with results
4. Synthesizes an answer with inline citations
5. Supports streaming responses and cross-session memory
"""

from __future__ import annotations

import json
import logging
from typing import Any

from research_agent.models import agenerate_text
from research_agent.chat.indexer import ChatLibraryIndex

logger = logging.getLogger(__name__)

# Tool definitions passed to the LLM so it can decide which to call
TOOL_DEFINITIONS = [
    {
        "name": "search_web",
        "description": "Search the web for current information on a topic. Use for recent developments, news, tutorials, and general knowledge.",
        "parameters": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results (1-10)",
                "default": 5,
            },
        },
    },
    {
        "name": "search_papers",
        "description": "Search academic papers (ArXiv, Semantic Scholar, OpenAlex) for a research topic. Use for finding peer-reviewed research, papers, citations.",
        "parameters": {
            "query": {
                "type": "string",
                "description": "The research query or paper title",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of papers (1-10)",
                "default": 5,
            },
        },
    },
    {
        "name": "discover_datasets",
        "description": "Find datasets on HuggingFace and Kaggle matching a research topic. Use when the user needs data for experiments or analysis.",
        "parameters": {
            "topic": {
                "type": "string",
                "description": "The research topic to find datasets for",
            },
        },
    },
    {
        "name": "query_library",
        "description": "Ask a question about documents in a previously uploaded PDF library. Use when the user asks about their uploaded papers.",
        "parameters": {
            "library_id": {
                "type": "string",
                "description": "The library ID from a previous PDF upload",
            },
            "question": {
                "type": "string",
                "description": "The question about the documents",
            },
        },
    },
    {
        "name": "launch_research",
        "description": "Launch a full research pipeline on a topic. This will decompose the topic, search multiple sources, synthesize findings, and generate a paper. Use when the user wants a comprehensive research paper.",
        "parameters": {
            "topic": {
                "type": "string",
                "description": "The research topic to investigate",
            },
            "depth": {
                "type": "string",
                "enum": ["quick", "balanced", "deep"],
                "description": "Research depth",
                "default": "balanced",
            },
        },
    },
]


def _format_tool_descriptions() -> str:
    """Format the tool definitions as a prompt string for the LLM."""
    lines = ["You have access to the following tools:\\n"]
    for tool in TOOL_DEFINITIONS:
        params: dict[str, Any] = tool["parameters"]  # type: ignore[assignment]
        param_str = ", ".join(
            f"{name}: {info.get('type', 'string')} - {info.get('description', '')}"
            for name, info in params.items()
        )
        lines.append(f"- **{tool['name']}**: {tool['description']}")
        lines.append(f"  Parameters: {param_str}")
        lines.append("")
    return "\\n".join(lines)

def _build_system_prompt(session_context: str = "") -> str:
    """Build the system prompt for the agent, including tool definitions."""
    return f"""You are an intelligent research assistant. Your role is to help users with research tasks 
by deciding which tools to use and synthesizing their results.

{_format_tool_descriptions()}

## Guidelines

1. **Analyze the query** - Determine what the user needs: web info, papers, datasets, or full research.
2. **Choose tools wisely** - Pick the most relevant tool(s). You can call multiple tools.
3. **Synthesize results** - Combine information from multiple tools into a coherent answer.
4. **Cite sources** - Always cite where information comes from using [1], [2] etc.
5. **Be concise** - Give clear, actionable answers. Use bullet points for lists.
6. **Acknowledge limitations** - If a tool returns no results, say so and suggest alternatives.

## Output Format

You MUST respond with a JSON object in this exact format:
{{
    "thought": "Your internal reasoning about what tools to call and why",
    "tool_calls": [
        {{
            "name": "tool_name",
            "parameters": {{ "param1": "value1" }}
        }}
    ],
    "message": "Your response to the user (use [1], [2] etc. for citations)"
}}

If no tools are needed, set tool_calls to an empty list [].
Return ONLY the JSON object, no other text.

{session_context}"""


async def _get_conversation_history(session_id: str, memory_store: dict[str, list[dict]]) -> list[dict]:
    """Get the conversation history for a session."""
    return memory_store.get(session_id, [])


async def _update_conversation_history(
    session_id: str,
    role: str,
    content: str,
    memory_store: dict[str, list[dict]],
    max_history: int = 20,
) -> None:
    """Add a message to the conversation history, trimming old messages."""
    if session_id not in memory_store:
        memory_store[session_id] = []
    memory_store[session_id].append({"role": role, "content": content})
    # Keep only the last max_history messages
    if len(memory_store[session_id]) > max_history:
        memory_store[session_id] = memory_store[session_id][-max_history:]


async def _execute_tool_call(
    tool_call: dict[str, Any],
    tool_registry: dict[str, Any],
    library_id: str | None = None,
) -> dict[str, Any]:
    """Execute a single tool call and return the result."""
    name = tool_call.get("name", "")
    params = tool_call.get("parameters", {})

    if name == "search_web":
        from research_agent.tools.web_search import DuckDuckGoAdapter
        adapter = DuckDuckGoAdapter()
        query = params.get("query", "")
        limit = min(int(params.get("limit", 5)), 10)
        result = await adapter.asearch(query, limit=limit)
        return {
            "tool": name,
            "items": [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("snippet", ""),
                }
                for item in result.items
            ],
        }

    elif name == "search_papers":
        from research_agent.tools.arxiv import ArxivAdapter
        from research_agent.tools.semantic_scholar import SemanticScholarAdapter
        from research_agent.tools.open_alex import OpenAlexAdapter

        query = params.get("query", "")
        limit = min(int(params.get("limit", 5)), 10)

        # Search multiple paper sources in parallel
        arxiv = ArxivAdapter()
        ss = SemanticScholarAdapter(api_key=None)  # type: ignore[call-arg]
        oa = OpenAlexAdapter()

        async def _search_arxiv():
            return await arxiv.asearch(query, limit=limit)

        async def _search_ss():
            return await ss.asearch(query, limit=limit)

        async def _search_oa():
            return await oa.asearch(query, limit=limit)

        import asyncio
        results = await asyncio.gather(
            _search_arxiv(), _search_ss(), _search_oa(),
            return_exceptions=True,
        )  # type: ignore[assignment]

        all_items = []
        seen_titles = set()
        for gather_result in results:
            if isinstance(gather_result, Exception):
                continue
            for item in gather_result.items:  # type: ignore[union-attr]
                title = (item.get("title") or "").strip().lower()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    all_items.append({
                        "title": item.get("title", ""),
                        "authors": item.get("authors", []),
                        "year": item.get("year", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("snippet", "") or item.get("content", ""),
                    })

        return {
            "tool": name,
            "items": all_items[:limit],
        }

    elif name == "discover_datasets":
        from research_agent.tools.huggingface import HuggingFaceDatasetAdapter
        from research_agent.tools.kaggle import KaggleDatasetAdapter

        topic = params.get("topic", "")
        hf = HuggingFaceDatasetAdapter()
        kaggle = KaggleDatasetAdapter()

        import asyncio
        hf_results = await asyncio.gather(
            hf.asearch(topic, limit=5),
            kaggle.asearch(topic, limit=5),
            return_exceptions=True,
        )  # type: ignore[assignment]
        hf_res = hf_results[0]  # type: ignore[index]
        kaggle_res = hf_results[1]  # type: ignore[index]

        all_datasets = []
        if not isinstance(hf_res, Exception):
            for item in hf_res.items:  # type: ignore[union-attr]
                all_datasets.append({
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "downloads": item.get("downloads", 0),
                    "url": item.get("url", ""),
                    "provider": "huggingface",
                })
        if not isinstance(kaggle_res, Exception):
            for item in kaggle_res.items:  # type: ignore[union-attr]
                all_datasets.append({
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "downloads": item.get("downloads", 0),
                    "url": item.get("url", ""),
                    "provider": "kaggle",
                })

        all_datasets.sort(key=lambda x: x.get("downloads", 0), reverse=True)
        return {"tool": name, "items": all_datasets[:10]}

    elif name == "query_library":
        lib_id = params.get("library_id", library_id or "")
        question = params.get("question", "")
        if lib_id and question:
            index = ChatLibraryIndex(lib_id)
            chunks = await index.search(question, limit=5)
            return {
                "tool": name,
                "items": [
                    {"text": c.get("text", "")[:500], "source": c.get("source_title", "") or c.get("source_url", "")}
                    for c in chunks
                ],
            }
        return {"tool": name, "items": [], "error": "No library_id or question provided"}

    elif name == "launch_research":
        return {
            "tool": name,
            "items": [{"topic": params.get("topic", ""), "depth": params.get("depth", "balanced")}],
            "note": "Full research pipeline launch requires the API endpoint. Use POST /api/chat/launch-research.",
        }

    return {"tool": name, "items": [], "error": f"Unknown tool: {name}"}


async def agent_chat(
    session_id: str,
    message: str,
    tool_registry: dict[str, Any] | None = None,
    library_id: str | None = None,
    memory_store: dict[str, list[dict]] | None = None,
    max_tool_iterations: int = 3,
) -> dict[str, Any]:
    """Run the agent loop: think → act → observe → respond.

    Args:
        session_id: Unique session identifier for conversation history.
        message: The user's message.
        tool_registry: Optional tool adapter registry (built from settings if None).
        library_id: Optional library ID for PDF querying.
        memory_store: In-memory conversation store (dict). Falls back to empty dict.
        max_tool_iterations: Maximum number of tool-calling iterations.

    Returns:
        Dict with 'message' (response text), 'tool_calls' (list of calls made),
        and 'citations' (source references).
    """
    if memory_store is None:
        memory_store = {}

    # Build conversation context from history
    history = await _get_conversation_history(session_id, memory_store)
    session_context = ""
    if history:
        recent = history[-6:]  # Last 3 exchanges (user+assistant)
        session_context = "## Recent Conversation\\n" + "\\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:200]}"
            for m in recent
        )

    system_prompt = _build_system_prompt(session_context)

    await _update_conversation_history(session_id, "user", message, memory_store)

    all_tool_calls: list[dict[str, Any]] = []
    all_citations: list[dict[str, str]] = []
    final_message = ""

    for iteration in range(max_tool_iterations):
        # Call the LLM with the tool definitions
        agent_prompt = f"""{system_prompt}

## User Query
{message}

## Previous Tool Results
{json.dumps(all_tool_calls, indent=2) if all_tool_calls else "No tools called yet."}

## Instructions
Respond with the JSON format specified above. Decide if you need to call more tools or if you have enough information to respond."""

        result = await agenerate_text(
            role="subagent",
            prompt=agent_prompt,
            temperature=0.3,
            max_tokens=2000,
        )

        if not result:
            final_message = "I encountered an error processing your request. Please try again."
            break

        # Parse the JSON response
        try:
            # Try to find JSON in the response
            text = result.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                parts = text.split("```")
                if len(parts) >= 3:
                    text = parts[1].strip()

            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                text = text[start : end + 1]

            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Failed to parse agent response as JSON: %s", e)
            final_message = result
            break

        thought = parsed.get("thought", "")
        tool_calls = parsed.get("tool_calls", [])
        message_part = parsed.get("message", "")

        if thought:
            logger.info("Agent thought: %s", thought)

        if not tool_calls:
            # Agent is done, use the message
            final_message = message_part
            break

        # Execute tool calls (can parallelize)
        import asyncio
        tool_results = await asyncio.gather(
            *[_execute_tool_call(tc, tool_registry or {}, library_id) for tc in tool_calls],
            return_exceptions=True,
        )

        for tc, tr in zip(tool_calls, tool_results):
            if isinstance(tr, Exception):
                all_tool_calls.append({
                    "tool": tc.get("name", ""),
                    "parameters": tc.get("parameters", {}),
                    "error": str(tr),
                })
            else:
                tr_dict: dict[str, Any] = tr  # type: ignore[assignment]
                all_tool_calls.append(tr_dict)
                items = tr_dict.get("items")
                if items:
                    for item in items:
                        cite = {
                            "source": tr_dict.get("tool", ""),
                            "title": item.get("title", item.get("name", "")),
                            "url": item.get("url", ""),
                        }
                        if cite["title"] or cite["url"]:
                            all_citations.append(cite)

    if not final_message:
        final_message = "I've gathered the available information. Here's what I found."

    # Build citations string
    citation_refs = []
    seen_urls = set()
    for i, c in enumerate(all_citations[:10], 1):
        if c["url"] and c["url"] not in seen_urls:
            seen_urls.add(c["url"])
            citation_refs.append(f"[{i}] {c['title']} - {c['url']}")

    await _update_conversation_history(session_id, "assistant", final_message, memory_store)

    return {
        "message": final_message,
        "tool_calls": all_tool_calls,
        "citations": citation_refs,
        "thought": thought if "thought" in locals() else "",
    }
