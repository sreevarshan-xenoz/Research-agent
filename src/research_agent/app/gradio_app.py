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

    task_lines = "\n".join(
        f"- {task.task_id}: {task.title} ({task.status})" for task in updated.tasks
    )
    note_lines = "\n".join(f"- {note}" for note in updated.critic_notes)
    warning_lines = "\n".join(f"- {warning}" for warning in updated.run_warnings[:10])
    section_lines = "\n".join(
        f"- {section.get('heading', 'Section')}: {section.get('content', '')[:120]}..."
        for section in updated.combined_sections
    )
    note_lines = note_lines or "- none"
    warning_lines = warning_lines or "- none"
    section_lines = section_lines or "- none"

    return (
        "Research run completed.\n"
        f"Topic: {updated.topic}\n"
        f"Template: {updated.template}\n"
        f"Phase: {updated.phase}\n\n"
        f"Runtime mode: {SETTINGS.runtime.mode}\n"
        f"Worker model: {SETTINGS.models.worker_model}\n"
        f"Strong model: {SETTINGS.models.strong_model}\n"
        f"Artifact directory: {updated.artifact_dir}\n\n"
        f"Tasks:\n{task_lines}\n\n"
        f"Critic notes:\n{note_lines}\n\n"
        f"Warnings:\n{warning_lines}\n\n"
        f"Sections:\n{section_lines}\n\n"
        "Generated files: main.tex, references.bib, compile_instructions.md, summary.json"
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
