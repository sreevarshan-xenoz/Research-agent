from research_agent.orchestration.nodes.clarifier import awaiting_user_node, clarifier_node
from research_agent.orchestration.state import GraphState
from research_agent.orchestration.nodes.combiner import combiner_node
from research_agent.orchestration.nodes.composer import composer_node
from research_agent.orchestration.nodes.citation_verifier import citation_verifier_node
from research_agent.orchestration.nodes.critic import critic_node
from research_agent.orchestration.nodes.dependency import (
	dependency_blocked_node,
	stop_node,
	workers_complete_node,
)
from research_agent.orchestration.nodes.exporter import exporter_node
from research_agent.orchestration.nodes.figure_generator import figure_generator_node
from research_agent.orchestration.nodes.peer_reviewer import peer_reviewer_node
from research_agent.orchestration.nodes.presentation import presentation_generator_node
from research_agent.orchestration.nodes.poster import poster_generator_node
from research_agent.orchestration.nodes.knowledge_graph import knowledge_graph_node
from research_agent.orchestration.nodes.bias_detector import bias_detector_node
from research_agent.orchestration.nodes.future_work import future_work_extrapolator_node
from research_agent.orchestration.nodes.comparison import comparison_table_node
from research_agent.orchestration.nodes.formula_normalizer import formula_normalizer_node
from research_agent.orchestration.nodes.hallucination_guard import hallucination_guard_node
from research_agent.orchestration.nodes.indexing import indexing_node
from research_agent.orchestration.nodes.intake import intake_node
from research_agent.orchestration.nodes.planner import planner_node
from research_agent.orchestration.nodes.worker import (
	get_pending_task_ids,
	get_ready_task_ids,
	make_worker_node,
)

__all__ = [
	"intake_node",
	"clarifier_node",
	"awaiting_user_node",
	"planner_node",
	"make_worker_node",
	"get_ready_task_ids",
	"get_pending_task_ids",
	"workers_complete_node",
	"dependency_blocked_node",
	"stop_node",
	"indexing_node",
	"critic_node",
	"combiner_node",
	"figure_generator_node",
	"citation_verifier_node",
	"composer_node",
	"formula_normalizer_node",
	"hallucination_guard_node",
	"peer_reviewer_node",
	"presentation_generator_node",
	"poster_generator_node",
	"knowledge_graph_node",
	"bias_detector_node",
	"future_work_extrapolator_node",
	"comparison_table_node",
	"exporter_node",
	"awaiting_user_critic_node",
]


async def awaiting_user_critic_node(state: GraphState) -> dict:
    """Pauses the graph to wait for user feedback on the critic's findings."""
    return {"phase": "awaiting_critic_review"}
