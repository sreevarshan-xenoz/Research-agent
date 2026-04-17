from __future__ import annotations

import uuid

import gradio as gr

from research_agent.config import load_settings
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.tools import build_tool_registry


SETTINGS = load_settings()
TOOL_REGISTRY = build_tool_registry(SETTINGS)


def run_placeholder(topic: str, template: str) -> str:
    topic = (topic or "").strip()
    if not topic:
        return "Please provide a research topic."

    initial_state = WorkflowState(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        topic=topic,
        template=template,
    )
    updated = run_graph(initial_state, registry=TOOL_REGISTRY)

    if updated.phase == "awaiting_user_clarification":
        questions = "\n".join(f"- {q}" for q in updated.clarification_questions)
        return (
            "Clarification required before planning.\n"
            f"Topic: {updated.topic}\n"
            f"Template: {updated.template}\n\n"
            f"Questions:\n{questions}"
        )

    task_lines = "\n".join(f"- {task.task_id}: {task.title}" for task in updated.tasks)
    return (
        "Initial orchestration complete.\n"
        f"Topic: {updated.topic}\n"
        f"Template: {updated.template}\n"
        f"Phase: {updated.phase}\n\n"
        f"Runtime mode: {SETTINGS.runtime.mode}\n"
        f"Worker model: {SETTINGS.models.worker_model}\n"
        f"Strong model: {SETTINGS.models.strong_model}\n\n"
        f"Planned tasks:\n{task_lines}"
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Research Agent v1") as demo:
        gr.Markdown("# Research Agent v1 (Scaffold)")
        topic = gr.Textbox(label="Research topic", lines=3)
        template = gr.Dropdown(
            choices=SETTINGS.output.supported_templates,
            value=SETTINGS.output.default_template,
            label="Template",
        )
        run_btn = gr.Button("Start")
        output = gr.Textbox(label="Status", lines=8)
        run_btn.click(fn=run_placeholder, inputs=[topic, template], outputs=[output])
    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch()
