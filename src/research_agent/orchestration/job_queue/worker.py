"""Standalone job queue worker process.

Run with:
    python -m research_agent.orchestration.job_queue.worker

This starts a worker that continuously polls the Redis queue for jobs
and executes them. Can be scaled horizontally by running multiple
instances.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from research_agent.orchestration.job_queue.manager import get_job_manager

logger = logging.getLogger(__name__)


async def _run_worker_async() -> None:
    """Run the worker process."""
    manager = get_job_manager()
    logger.info("Worker process starting...")

    # Register default handlers
    _register_handlers(manager)

    # Handle shutdown signals
    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received, stopping worker...")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (ValueError, NotImplementedError):
            pass  # Not all platforms support signal handlers

    # Start logging
    from research_agent.config import load_settings
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.observability.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        # Run the worker loop as a task
        worker_task = asyncio.create_task(manager.run_worker(poll_interval=1.0))

        # Wait for shutdown
        await shutdown_event.wait()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
    finally:
        await manager.close()
        logger.info("Worker process stopped.")


def _register_handlers(manager) -> None:
    """Register default job handlers."""
    from research_agent.orchestration.job_queue.models import JobType

    # Research run handler
    async def handle_research_run(job, mgr):
        from research_agent.orchestration.graph import run_graph
        from research_agent.orchestration.state import WorkflowState
        from research_agent.tools.registry import build_tool_registry
        from research_agent.config import load_settings

        settings = load_settings()
        tool_registry = build_tool_registry(settings)

        params = job.params
        state = WorkflowState(
            run_id=job.run_id or f"run-job-{job.job_id}",
            topic=params.get("topic", ""),
            template=params.get("template", "ieee"),
            language=params.get("language", "en"),
            depth=params.get("depth", "balanced"),
            autonomy_mode=params.get("autonomy_mode", "hybrid"),
            max_runtime_minutes=int(params.get("max_runtime_minutes", settings.runtime.max_runtime_minutes)),
            max_cost_usd=float(params.get("max_cost_usd", settings.runtime.max_cost_usd)),
            max_iterations=int(params.get("max_iterations", settings.runtime.max_iterations)),
        )

        final_state = await run_graph(state, registry=tool_registry)

        return {
            "run_id": final_state.run_id,
            "phase": final_state.phase,
            "stop_reason": final_state.stop_reason,
            "section_confidence": final_state.section_confidence,
        }

    # Export handler
    async def handle_export(job, mgr):
        from research_agent.config import load_settings
        from pathlib import Path

        params = job.params
        run_id = params.get("run_id", job.run_id)
        export_format = params.get("format", "blog")
        topic = params.get("topic", "")
        settings_local = load_settings()
        artifact_root = getattr(settings_local.output, "artifact_root", ".runtime/artifacts")

        if export_format == "blog":
            from research_agent.output.blog_generator import generate_all

            run_dir = Path(artifact_root) / run_id
            tex_path = run_dir / "main.tex"
            if not tex_path.exists():
                raise FileNotFoundError(f"Run artifacts not found: {run_id}")

            tex_content = tex_path.read_text(encoding="utf-8")
            formats = params.get("formats", ["blog", "newsletter", "twitter"])
            output = generate_all(tex_content, topic, formats=formats)

            blog_dir = run_dir / "blog"
            blog_dir.mkdir(parents=True, exist_ok=True)
            for fmt, content in output.items():
                (blog_dir / f"{fmt}.md").write_text(
                    "\n\n".join(content) if isinstance(content, list) else content,
                    encoding="utf-8",
                )

            return {"formats": list(output.keys()), "path": str(blog_dir)}

        elif export_format == "pdf":
            from research_agent.output.pdf_renderer import compile_pdf
            from pathlib import Path

            run_dir = Path(".runtime/artifacts") / run_id
            pdf_path = compile_pdf(run_dir)
            return {"pdf_path": str(pdf_path) if pdf_path else None}

        return {"error": f"Unknown export format: {export_format}"}

    # Watchdog check handler
    async def handle_watchdog(job, mgr):
        from research_agent.orchestration.watchdog import run_all_due_checks
        from research_agent.tools.registry import build_tool_registry
        from research_agent.config import load_settings

        settings = load_settings()
        tool_registry = build_tool_registry(settings)
        digests = await run_all_due_checks(tool_registry)
        return {
            "profiles_checked": len(digests),
            "total_new_papers": sum(d.paper_count for d in digests),
        }

    manager.register_handler(JobType.RESEARCH_RUN, handle_research_run)
    manager.register_handler(JobType.EXPORT_BLOG, handle_export)
    manager.register_handler(JobType.EXPORT_PDF, handle_export)
    manager.register_handler(JobType.WATCHDOG_CHECK, handle_watchdog)


def main() -> None:
    """Entry point for the worker process."""
    from research_agent.config import load_settings

    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.observability.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    asyncio.run(_run_worker_async())


if __name__ == "__main__":
    main()
