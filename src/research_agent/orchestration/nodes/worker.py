from __future__ import annotations

import asyncio

from research_agent.observability import apublish_progress
from research_agent.observability.progress import ProgressCallback, get_progress_callback
from research_agent.orchestration.state import GraphState
from research_agent.tools.base import BaseToolAdapter
from research_agent.tools.registry import arun_multi_source_search

WEB_SOURCE_TYPES = {"web", "web_scrape", "browser"}


def get_ready_task_ids(tasks: list[dict[str, object]]) -> list[str]:
    status_by_id = {str(task["task_id"]): str(task["status"]) for task in tasks}
    ready_ids: list[str] = []

    for task in tasks:
        if str(task["status"]) != "pending":
            continue
        dependencies = [str(dep) for dep in task.get("depends_on", [])]
        if all(status_by_id.get(dep) == "complete" for dep in dependencies):
            ready_ids.append(str(task["task_id"]))

    return ready_ids


def get_pending_task_ids(tasks: list[dict[str, object]]) -> list[str]:
    return [str(task["task_id"]) for task in tasks if str(task["status"]) == "pending"]


async def _enrich_web_results_with_page_content(
    result_map: dict[str, object],
    registry: dict[str, BaseToolAdapter],
    *,
    max_pages_per_provider: int = 2,
) -> None:
    page_fetcher = registry.get("page_fetcher")
    if page_fetcher is None:
        return

    async def fetch_item(item: dict[str, object]) -> None:
        url = str(item.get("url") or "").strip()
        if not url or item.get("content"):
            return
        fetched = await page_fetcher.asearch(url, limit=1)
        if fetched.items:
            page = fetched.items[0]
            if page.get("content"):
                item["content"] = page["content"]
            if not item.get("title") and page.get("title"):
                item["title"] = page["title"]
        if fetched.warnings:
            existing = item.setdefault("fetch_warnings", [])
            if isinstance(existing, list):
                existing.extend(fetched.warnings)

    tasks = []
    for result in result_map.values():
        items = getattr(result, "items", [])
        queued_for_provider = 0
        for item in items:
            if queued_for_provider >= max_pages_per_provider:
                break
            if not isinstance(item, dict):
                continue
            if str(item.get("source_type") or "") not in WEB_SOURCE_TYPES:
                continue
            tasks.append(fetch_item(item))
            queued_for_provider += 1

    if tasks:
        await asyncio.gather(*tasks)


async def _emit_progress(
    callback: ProgressCallback | None,
    *,
    agent: str,
    status: str,
    detail: str,
    message: str,
) -> None:
    if callback is not None:
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(
                    {
                        "agent": agent,
                        "status": status,
                        "detail": detail,
                        "message": message,
                    }
                )
            else:
                callback(
                    {
                        "agent": agent,
                        "status": status,
                        "detail": detail,
                        "message": message,
                    }
                )
            return
        except Exception:
            pass

    await apublish_progress(agent=agent, status=status, detail=detail, message=message)


def make_worker_node(registry: dict[str, BaseToolAdapter]):
    registry_provider_count = max(len(registry), 1)

    async def worker_node(state: GraphState) -> dict:
        tasks = [dict(task) for task in state["tasks"]]
        if not tasks:
            return {"phase": "workers_idle"}

        ready_task_ids = get_ready_task_ids(tasks)
        if not ready_task_ids:
            return {"phase": "workers_idle"}

        findings = dict(state["task_findings"])
        run_warnings = list(state["run_warnings"])
        estimated_cost_usd = float(state.get("estimated_cost_usd", 0.0) or 0.0)
        progress_handler = get_progress_callback()

        async def execute_single_task(task: dict[str, object]) -> tuple[str, dict[str, object], list[str]]:
            task_id = str(task["task_id"])
            task["status"] = "running"
            await _emit_progress(
                progress_handler,
                agent=f"SubResearch {task_id}",
                status="running",
                detail=str(task["title"]),
                message=f"Running {task_id}",
            )
            query = str(task["objective"])
            providers = task.get("providers")
            result_map = await arun_multi_source_search(query, registry, limit=4, providers=providers)
            await _enrich_web_results_with_page_content(result_map, registry)
            
            task_finding = {
                provider: {
                    "item_count": len(result.items),
                    "metadata_only_count": sum(
                        1
                        for item in result.items
                        if isinstance(item, dict)
                        and not str(item.get("snippet") or item.get("content") or "").strip()
                    ),
                    "warning_count": len(result.warnings),
                    "warnings": result.warnings,
                    "items": result.items,
                }
                for provider, result in result_map.items()
            }
            
            task_warnings = []
            for provider, result in result_map.items():
                for warning in result.warnings:
                    task_warnings.append(f"{provider}:{warning}")
            
            task["status"] = "complete"
            await _emit_progress(
                progress_handler,
                agent=f"SubResearch {task_id}",
                status="complete",
                detail=f"{task['title']} ({sum(len(result.items) for result in result_map.values())} items)",
                message=f"Completed {task_id}",
            )
            return task_id, task_finding, task_warnings

        # Execute all ready tasks in parallel
        ready_tasks = [t for t in tasks if str(t["task_id"]) in ready_task_ids]
        
        results = await asyncio.gather(*(execute_single_task(t) for t in ready_tasks))

        # Rough cost estimator for provider API usage in v1.
        estimated_cost_usd += len(ready_tasks) * registry_provider_count * 0.01
            
        for task_id, task_finding, task_warnings in results:
            findings[task_id] = task_finding
            run_warnings.extend(task_warnings)

        return {
            "tasks": tasks,
            "task_findings": findings,
            "phase": "workers_executed",
            "run_warnings": run_warnings,
            "estimated_cost_usd": round(estimated_cost_usd, 4),
            "stop_reason": None,
        }

    return worker_node
