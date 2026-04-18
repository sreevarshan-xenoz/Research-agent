from __future__ import annotations

from research_agent.observability import publish_progress
from research_agent.observability.progress import ProgressCallback, get_progress_callback
from research_agent.orchestration.state import GraphState
from research_agent.tools.base import BaseToolAdapter
from research_agent.tools.registry import run_multi_source_search


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


from concurrent.futures import ThreadPoolExecutor


def _emit_progress(
    callback: ProgressCallback | None,
    *,
    agent: str,
    status: str,
    detail: str,
    message: str,
) -> None:
    if callback is not None:
        try:
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

    publish_progress(agent=agent, status=status, detail=detail, message=message)


def make_worker_node(registry: dict[str, BaseToolAdapter]):
    def worker_node(state: GraphState) -> dict:
        tasks = [dict(task) for task in state["tasks"]]
        if not tasks:
            return {"phase": "workers_idle"}

        ready_task_ids = get_ready_task_ids(tasks)
        if not ready_task_ids:
            return {"phase": "workers_idle"}

        findings = dict(state["task_findings"])
        run_warnings = list(state["run_warnings"])
        progress_handler = get_progress_callback()

        def execute_single_task(task: dict[str, object]) -> tuple[str, dict[str, object], list[str]]:
            task_id = str(task["task_id"])
            task["status"] = "running"
            _emit_progress(
                progress_handler,
                agent=f"SubResearch {task_id}",
                status="running",
                detail=str(task["title"]),
                message=f"Running {task_id}",
            )
            query = str(task["objective"])
            result_map = run_multi_source_search(query, registry, limit=4)
            
            task_finding = {
                provider: {
                    "item_count": len(result.items),
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
            _emit_progress(
                progress_handler,
                agent=f"SubResearch {task_id}",
                status="complete",
                detail=f"{task['title']} ({sum(len(result.items) for result in result_map.values())} items)",
                message=f"Completed {task_id}",
            )
            return task_id, task_finding, task_warnings

        # Execute all ready tasks in parallel
        ready_tasks = [t for t in tasks if str(t["task_id"]) in ready_task_ids]
        
        with ThreadPoolExecutor(max_workers=len(ready_tasks) or 1) as executor:
            results = list(executor.map(execute_single_task, ready_tasks))
            
        for task_id, task_finding, task_warnings in results:
            findings[task_id] = task_finding
            run_warnings.extend(task_warnings)

        return {
            "tasks": tasks,
            "task_findings": findings,
            "phase": "workers_executed",
            "run_warnings": run_warnings,
            "stop_reason": None,
        }

    return worker_node
