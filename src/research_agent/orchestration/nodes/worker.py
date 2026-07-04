from __future__ import annotations

import asyncio
from typing import Any, cast

import logging

from research_agent.observability import apublish_progress
from research_agent.observability.logging import ErrorSeverity, log_error
from research_agent.observability.progress import ProgressCallback, get_progress_callback
from research_agent.orchestration.state import GraphState, GraphTask
from research_agent.tools.base import BaseToolAdapter
from research_agent.tools.registry import arun_multi_source_search
from research_agent.rag.table_extractor import extract_tables_from_text


logger = logging.getLogger(__name__)

WEB_SOURCE_TYPES = {"web", "web_scrape", "browser"}


def get_ready_task_ids(tasks: list[GraphTask]) -> list[str]:
    status_by_id = {str(task["task_id"]): str(task["status"]) for task in tasks}
    ready_ids: list[str] = []

    for task in tasks:
        if str(task["status"]) != "pending":
            continue
        deps = task.get("depends_on")
        dependencies = [str(dep) for dep in deps] if isinstance(deps, list) else []
        if all(status_by_id.get(dep) == "complete" for dep in dependencies):
            ready_ids.append(str(task["task_id"]))

    return ready_ids


def get_pending_task_ids(tasks: list[GraphTask]) -> list[str]:
    return [str(task["task_id"]) for task in tasks if str(task["status"]) == "pending"]


async def _enrich_web_results_with_page_content(
    result_map: dict[str, Any],
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
                content = str(page["content"])
                item["content"] = content
                # Extract tables
                try:
                    tables = await extract_tables_from_text(content)
                    if tables:
                        item["tables"] = tables
                except Exception as exc:
                    log_error(
                        "Table extraction failed",
                        severity=ErrorSeverity.RECOVERABLE,
                        component="worker",
                        detail=type(exc).__name__,
                    )
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
        except Exception as exc:
            log_error(
                "Progress callback failed",
                severity=ErrorSeverity.RECOVERABLE,
                component="worker",
                detail=f"{type(exc).__name__}: {exc}",
            )

    await apublish_progress(agent=agent, status=status, detail=detail, message=message)


async def _run_deep_research_task(
    task: GraphTask,
    registry: dict[str, BaseToolAdapter],
    progress_handler: ProgressCallback | None,
    task_id: str,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Execute a deep research task with iterative query refinement and citation chaining.

    Multi-round search: initial pass -> gap analysis -> follow-up queries ->
    citation chaining -> merge findings.
    """
    from research_agent.config import load_settings
    from research_agent.orchestration.deep_research.query_refiner import refine_queries
    from research_agent.orchestration.deep_research.citation_chainer import chain_citations

    settings = load_settings()
    dr_settings = settings.deep_research
    max_rounds = dr_settings.max_search_rounds

    query = str(task["objective"])
    providers_raw = task.get("providers")
    providers = [str(p) for p in providers_raw] if isinstance(providers_raw, list) else None

    aggregated_findings: dict[str, dict[str, Any]] = {}
    queries_used: list[str] = [query]
    task_warnings: list[str] = []

    for round_idx in range(max_rounds):
        await _emit_progress(
            progress_handler,
            agent=f"DeepResearch {task_id}",
            status="running",
            detail=f"Round {round_idx + 1}/{max_rounds}: {query[:80]}",
            message=f"Deep research round {round_idx + 1}",
        )

        try:
            result_map = await arun_multi_source_search(
                query, registry, limit=4, providers=providers
            )

            try:
                await _enrich_web_results_with_page_content(result_map, registry)
            except Exception as enrichment_exc:
                task_warnings.append(f"enrichment_error:{str(enrichment_exc)}")

            # Merge round findings into aggregated findings
            for provider, result in result_map.items():
                if provider in aggregated_findings:
                    existing_items = aggregated_findings[provider].get("items", [])
                    existing_ids = {str(item.get("paper_id", item.get("url", ""))) for item in existing_items if isinstance(item, dict)}
                    for item in result.items:
                        if isinstance(item, dict):
                            item_id = str(item.get("paper_id", item.get("url", "")))
                            if item_id not in existing_ids:
                                existing_items.append(item)
                                existing_ids.add(item_id)
                    aggregated_findings[provider]["items"] = existing_items
                    aggregated_findings[provider]["item_count"] = len(existing_items)
                else:
                    metadata_only = sum(
                        1 for item in result.items
                        if isinstance(item, dict) and not str(item.get("snippet") or item.get("content") or "").strip()
                    )
                    aggregated_findings[provider] = {
                        "item_count": len(result.items),
                        "metadata_only_count": metadata_only,
                        "warning_count": len(result.warnings),
                        "warnings": list(result.warnings),
                        "items": list(result.items),
                    }

                for warning in result.warnings:
                    task_warnings.append(f"{provider}:{warning}")
        except Exception as search_exc:
            task_warnings.append(f"deep_search_round_{round_idx}_error:{search_exc}")
            logger.exception("Deep search round %d failed for task %s", round_idx, task_id)

        # Query refinement: generate follow-up queries from gaps
        if round_idx < max_rounds - 1:
            follow_up_queries = await refine_queries(
                topic=str(task.get("title", "")),
                task_title=str(task.get("title", "")),
                task_objective=query,
                current_findings=aggregated_findings,
                queries_used=queries_used,
            )
            if follow_up_queries:
                query = follow_up_queries[0]
                queries_used.append(query)
                if len(follow_up_queries) > 1:
                    queries_used.append(follow_up_queries[1])
            else:
                break  # No more gaps to explore

    # Citation chaining: find cited/citing papers for high-value seeds
    try:
        chain_result = await chain_citations(
            registry=registry,
            task_findings=aggregated_findings,
            max_depth=dr_settings.max_citation_chain_depth,
            max_seed_papers=dr_settings.max_seed_papers,
            max_total=dr_settings.max_chained_papers,
        )
        if chain_result.chained_papers:
            aggregated_findings.setdefault("citation_chain", {
                "item_count": len(chain_result.chained_papers),
                "items": chain_result.chained_papers,
                "warning_count": 0,
                "warnings": [],
                "metadata_only_count": 0,
            })
            task_warnings.extend(chain_result.warnings)
    except Exception as chain_exc:
        task_warnings.append(f"citation_chaining_error:{chain_exc}")

    return aggregated_findings, task_warnings


class WorkerPool:
    """Manages parallel execution of research tasks with concurrency control."""

    def __init__(self, max_workers: int = 4):
        self.semaphore = asyncio.Semaphore(max_workers)

    async def execute_task(
        self, 
        task: GraphTask, 
        registry: dict[str, BaseToolAdapter],
        progress_handler: ProgressCallback | None = None,
        *,
        deep_research_enabled: bool = False,
    ) -> tuple[str, dict[str, dict[str, Any]], list[str]]:
        async with self.semaphore:
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
            providers_raw = task.get("providers")
            providers = [str(p) for p in providers_raw] if isinstance(providers_raw, list) else None

            task_finding: dict[str, dict[str, Any]] = {}
            task_warnings: list[str] = []

            if deep_research_enabled:
                # P21: Deep research with iterative refinement + citation chaining
                task_finding, task_warnings = await _run_deep_research_task(
                    task, registry, progress_handler, task_id
                )
            else:
                # Standard single-pass search
                try:
                    result_map = await arun_multi_source_search(
                        query, registry, limit=4, providers=providers
                    )

                    try:
                        await _enrich_web_results_with_page_content(result_map, registry)
                    except Exception as enrichment_exc:
                        task_warnings.append(f"enrichment_error:{str(enrichment_exc)}")
                        log_error(
                            "Page enrichment failed for task %s",
                            severity=ErrorSeverity.RECOVERABLE,
                            component="worker",
                            trace_id=task_id,
                            detail=str(enrichment_exc),
                        )

                    task_finding = {
                        provider: {
                            "item_count": len(result.items),
                            "metadata_only_count": sum(
                                1 for item in result.items
                                if isinstance(item, dict)
                                and not str(item.get("snippet") or item.get("content") or "").strip()
                            ),
                            "warning_count": len(result.warnings),
                            "warnings": result.warnings,
                            "items": result.items,
                        }
                        for provider, result in result_map.items()
                    }

                    for provider, result in result_map.items():
                        for warning in result.warnings:
                            task_warnings.append(f"{provider}:{warning}")

                except Exception as search_exc:
                    logger.exception("Catastrophic search failure for task %s", task_id)
                    task_warnings.append(f"search_catastrophic_error:{str(search_exc)}")
                    task_finding = {"error": {"items": [], "warnings": [str(search_exc)], "item_count": 0}}

            task["status"] = "complete"
            total_items = sum(
                int(f["item_count"])
                for f in task_finding.values()
                if isinstance(f, dict) and "item_count" in f
            )
            await _emit_progress(
                progress_handler,
                agent=f"SubResearch {task_id}",
                status="complete",
                detail=f"{task['title']} ({total_items} items)",
                message=f"Completed {task_id}",
            )
            return task_id, task_finding, task_warnings


def make_worker_node(registry: dict[str, BaseToolAdapter]):
    from research_agent.config import load_settings
    settings = load_settings()
    max_workers = settings.runtime.parallel_workers
    pool = WorkerPool(max_workers=max_workers)
    
    registry_provider_count = max(len(registry), 1)
    deep_research_enabled = settings.deep_research.enabled

    async def worker_node(state: GraphState) -> dict:
        tasks: list[GraphTask] = [cast(GraphTask, dict(task)) for task in state["tasks"]]
        if not tasks:
            return {"phase": "workers_idle"}

        ready_task_ids = get_ready_task_ids(tasks)
        if not ready_task_ids:
            return {"phase": "workers_idle"}

        findings = dict(state["task_findings"])
        run_warnings = list(state["run_warnings"])
        estimated_cost_usd = float(state.get("estimated_cost_usd", 0.0) or 0.0)
        progress_handler = get_progress_callback()
        search_rounds = dict(state.get("search_rounds", {}))

        ready_tasks = [t for t in tasks if str(t["task_id"]) in ready_task_ids]

        execution_tasks = [
            pool.execute_task(
                t, registry, progress_handler,
                deep_research_enabled=deep_research_enabled,
            )
            for t in ready_tasks
        ]

        results = await asyncio.gather(*execution_tasks, return_exceptions=True)

        estimated_cost_usd += len(ready_tasks) * registry_provider_count * 0.01
            
        for result in results:
            if isinstance(result, BaseException):
                run_warnings.append(f"worker_task_fatal:{result}")
                log_error(
                    "Worker task raised exception",
                    severity=ErrorSeverity.FATAL,
                    component="worker",
                    detail=str(result),
                )
                continue
            task_id, task_finding, task_warnings = result
            findings[task_id] = task_finding
            run_warnings.extend(task_warnings)

        return {
            "tasks": tasks,
            "task_findings": findings,
            "phase": "workers_executed",
            "run_warnings": run_warnings,
            "estimated_cost_usd": round(estimated_cost_usd, 4),
            "stop_reason": None,
            "search_rounds": search_rounds,
        }

    return worker_node
