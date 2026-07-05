from __future__ import annotations

from research_agent.models import agenerate_text, run_ensemble
from research_agent.observability import apublish_progress
from research_agent.orchestration.state import GraphState


async def bias_detector_node(state: GraphState) -> dict:
    """Analyzes retrieved sources for institutional, geographic, or citation bias."""
    await apublish_progress(
        agent="Bias Detector",
        status="running",
        detail="Analyzing source distribution",
        message="Running bias detection pass",
    )
    
    findings = state.get("task_findings", {})
    if not findings:
        return {"phase": "bias_skipped"}

    # Collect source metadata
    sources = []
    for task_id, providers in findings.items():
        for provider, data in providers.items():
            items = data.get("items", [])
            if isinstance(items, list):
                for item in items:
                    sources.append({
                        "title": item.get("title"),
                        "authors": item.get("authors"),
                        "venue": item.get("venue") or item.get("journal"),
                        "year": item.get("year"),
                        "publisher": item.get("publisher"),
                    })

    # Summarize sources for the LLM
    source_summary = "\n".join([
        f"- {s['title']} ({s['year']}) | Venue: {s['venue']} | Publisher: {s['publisher']}"
        for s in sources[:30] # Limit to top 30
    ])

    prompt = (
        "You are an academic ethics and bibliometrics expert. Analyze the following list of cited sources for potential biases.\n\n"
        f"Topic: {state['topic']}\n\n"
        "Source List:\n"
        f"{source_summary}\n\n"
        "Instructions:\n"
        "1. Identify any 'institutional bubbles' (e.g., too many papers from one university or tech company).\n"
        "2. Identify any geographic bias (e.g., Western-centric vs. Global South representation).\n"
        "3. Check for recency bias or lack of foundational/historical context.\n"
        "4. Provide a structured 'Bias Detection Report' in Markdown.\n"
        "5. If the source distribution looks healthy and balanced, state that clearly.\n"
    )

    # P31: Multi-Model Ensemble Voting for bias detection
    from research_agent.config import load_settings
    _settings = load_settings()
    ensemble_enabled = _settings.ensemble.enabled and "bias_detection" in _settings.ensemble.task_overrides

    bias_report = None
    if ensemble_enabled:
        ensemble_result = await run_ensemble(
            task_type="bias_detection",
            prompt=prompt,
            temperature=0.3,
            max_tokens=1500,
        )
        if ensemble_result.num_success >= 2:
            bias_report = ensemble_result.aggregated_text

    if bias_report is None:
        bias_report = await agenerate_text(
            role="orchestrator",
            prompt=prompt,
            temperature=0.3,
            max_tokens=1500
        )

    await apublish_progress(
        agent="Bias Detector",
        status="complete",
        detail="Bias report generated",
        message="Analysis complete",
    )
    
    return {
        "bias_report": bias_report,
        "phase": "bias_detected"
    }
