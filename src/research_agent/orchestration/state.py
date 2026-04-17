from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SubtopicTask:
    task_id: str
    title: str
    objective: str
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"


@dataclass
class WorkflowState:
    run_id: str
    topic: str
    template: str = "ieee"
    phase: str = "intake"
    iteration_index: int = 0
    stop_reason: Optional[str] = None
    tasks: List[SubtopicTask] = field(default_factory=list)
    section_confidence: Dict[str, float] = field(default_factory=dict)
