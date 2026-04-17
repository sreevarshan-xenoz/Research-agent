from __future__ import annotations

import gradio as gr


def run_placeholder(topic: str, template: str) -> str:
    topic = (topic or "").strip()
    if not topic:
        return "Please provide a research topic."
    return (
        "Scaffold ready.\\n"
        f"Topic: {topic}\\n"
        f"Template: {template}\\n\\n"
        "Next step: wire orchestration graph execution into this handler."
    )


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Research Agent v1") as demo:
        gr.Markdown("# Research Agent v1 (Scaffold)")
        topic = gr.Textbox(label="Research topic", lines=3)
        template = gr.Dropdown(choices=["ieee", "acm"], value="ieee", label="Template")
        run_btn = gr.Button("Start")
        output = gr.Textbox(label="Status", lines=8)
        run_btn.click(fn=run_placeholder, inputs=[topic, template], outputs=[output])
    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch()
