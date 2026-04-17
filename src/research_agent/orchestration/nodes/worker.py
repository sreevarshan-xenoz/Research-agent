from __future__ import annotations

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


def make_worker_node(registry: dict[str, BaseToolAdapter]):
    def worker_node(state: GraphState) -> dict:
        tasks = [dict(task) for task in state["tasks"]]
        if not tasks:
            return {"phase": "workers_idle"}

        ready_task_ids = get_ready_task_ids(tasks)
        if not ready_task_ids:
            return {"phase": "workers_idle"}

        findings = dict(state["task_findings"])

        for task in tasks:
            task_id = str(task["task_id"])
            if task_id not in ready_task_ids:
                continue

            query = str(task["objective"])
            result_map = run_multi_source_search(query, registry, limit=4)
            findings[task_id] = {
                provider: {
                    "item_count": len(result.items),
                    "warning_count": len(result.warnings),
                    "warnings": result.warnings,
                }
                for provider, result in result_map.items()
            }
            task["status"] = "complete"

        return {
            "tasks": tasks,
            "task_findings": findings,
            "phase": "workers_executed",
            "stop_reason": None,
        }

    return worker_node
