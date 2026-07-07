"""
P19: Plugin System

Entry-point based plugin discovery via Python namespace packages,
plugin lifecycle hooks (on_run_start, on_section_generated, on_run_complete),
sandboxed execution, and a plugin browser UI.

Plugins live under the `research_agent.plugins` namespace and are
discovered via:
1. Python entry points (pyproject.toml `[project.entry-points."research_agent.plugins"]`)
2. Filesystem scanning of `src/research_agent/plugins/installed/`
"""
