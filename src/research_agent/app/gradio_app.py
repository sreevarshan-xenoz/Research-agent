from __future__ import annotations

import uuid

import gradio as gr

from research_agent.config import load_settings
from research_agent.orchestration.graph import run_graph
from research_agent.orchestration.state import WorkflowState
from research_agent.tools import build_tool_registry


SETTINGS = load_settings()
TOOL_REGISTRY = build_tool_registry(SETTINGS)


async def run_research(topic: str, template: str) -> str:
    topic = (topic or "").strip()
    if not topic:
        return "⚠️ Please provide a research topic."

    # v2 uses load_settings() to get current provider info
    settings = load_settings()
    provider_info = f"Orchestrator: {settings.models.orchestrator_provider} ({settings.models.orchestrator_model})"
    worker_info = f"Workers: {settings.runtime.parallel_workers} (Parallel)"

    initial_state = WorkflowState(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        topic=topic,
        template=template,
    )
    
    try:
        updated = await run_graph(initial_state, registry=TOOL_REGISTRY)
    except Exception as e:
        return f"❌ Error during execution: {str(e)}"

    header = f"🚀 {provider_info} | {worker_info}\n"
    header += "=" * 60 + "\n"

    if updated.phase == "awaiting_user_clarification":
        questions = "\n".join(f"❓ {q}" for q in updated.clarification_questions)
        return (
            header +
            "🔍 Clarification required before planning.\n"
            f"Topic: {updated.topic}\n"
            f"Template: {updated.template}\n\n"
            f"Questions:\n{questions}"
        )

    task_lines = "\n".join(
        f"- {task.task_id}: {task.title} ({task.status})" for task in updated.tasks
    )
    
    # Format warnings with emoji
    warning_lines = ""
    if updated.run_warnings:
        warning_lines = "\n⚠️ Warnings:\n" + "\n".join(f"  • {w}" for w in updated.run_warnings[:10])
    
    note_lines = "\n".join(f"📝 {note}" for note in updated.critic_notes)
    section_lines = "\n".join(
        f"📄 {section.get('heading', 'Section')}: {len(section.get('content', ''))} chars"
        for section in updated.combined_sections
    )
    
    note_lines = note_lines or "📝 No critic notes."
    section_lines = section_lines or "📄 No sections generated."

    status_msg = "✅ Research run completed successfully."
    if updated.stop_reason and updated.stop_reason != "completed":
        status_msg = f"🛑 Run stopped: {updated.stop_reason}"

    return (
        header +
        f"{status_msg}\n"
        f"Topic: {updated.topic}\n"
        f"Phase: {updated.phase}\n\n"
        f"📂 Artifacts: {updated.artifact_dir}\n"
        f"⏱️ Elapsed: {round(time.time() - updated.started_at, 1)}s\n\n"
        f"Tasks:\n{task_lines}\n"
        f"{warning_lines}\n\n"
        f"Critic Notes:\n{note_lines}\n\n"
        f"Sections:\n{section_lines}\n\n"
        "✨ Files generated: main.tex, references.bib, compile_instructions.md"
    )


def build_app() -> gr.Blocks:
    settings = load_settings()
    with gr.Blocks(title="Research Agent v2", theme=gr.themes.Soft()) as demo:
        gr.Markdown(f"# 🔬 Research Agent v2")
        gr.Markdown(f"**Mode:** {settings.runtime.mode} | **Parallel Workers:** {settings.runtime.parallel_workers}")
        
        with gr.Row():
            with gr.Column(scale=1):
                topic = gr.Textbox(
                    label="Research Topic / Question", 
                    placeholder="e.g., Comparing CRISPR-Cas9 efficiency in therapeutic applications",
                    lines=5
                )
                template = gr.Dropdown(
                    choices=settings.output.supported_templates,
                    value=settings.output.default_template,
                    label="LaTeX Template",
                )
                run_btn = gr.Button("🚀 Start Research", variant="primary")
            
            with gr.Column(scale=2):
                output = gr.Textbox(label="Execution Workbench", lines=25, interactive=False)
        
        run_btn.click(fn=run_research, inputs=[topic, template], outputs=[output])
    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch()
