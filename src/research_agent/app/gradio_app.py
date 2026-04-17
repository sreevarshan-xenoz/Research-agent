from __future__ import annotations

import gradio as gr

from research_agent.config import load_settings


SETTINGS = load_settings()


def run_placeholder(topic: str, template: str) -> str:
    topic = (topic or "").strip()
    if not topic:
        return "Please provide a research topic."
    return (
        "Scaffold ready.\\n"
        f"Topic: {topic}\\n"
        f"Template: {template}\\n\\n"
        f"Runtime mode: {SETTINGS.runtime.mode}\\n"
        f"Worker model: {SETTINGS.models.worker_model}\\n"
        f"Strong model: {SETTINGS.models.strong_model}\\n\\n"
        "Next step: wire orchestration graph execution into this handler."
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
