from __future__ import annotations

from typing import Any


STRATEGY_KEYWORDS = {
    "methodology": ["method", "approach", "architecture", "algorithm", "framework"],
    "population": ["dataset", "participants", "cohort", "population", "sample"],
    "evaluation": ["accuracy", "precision", "recall", "f1", "metric", "benchmark"],
    "temporal": ["recent", "state-of-the-art", "latest"],
}


class GapAnalyzer:
    def analyze(self, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        if not papers:
            return gaps

        methods = set()
        populations = set()
        evaluations = set()
        years = []

        for paper in papers:
            text = (paper.get("abstract", "") + " " + paper.get("content", "")).lower()
            for strategy, keywords in STRATEGY_KEYWORDS.items():
                found = [kw for kw in keywords if kw in text]
                if strategy == "methodology":
                    methods.update(found)
                elif strategy == "population":
                    populations.update(found)
                elif strategy == "evaluation":
                    evaluations.update(found)
            year = paper.get("year")
            if year:
                years.append(int(year))

        if len(papers) < 5:
            gaps.append({
                "category": "coverage",
                "description": f"Only {len(papers)} papers analyzed. More sources needed for comprehensive gap analysis.",
                "confidence": 0.3,
                "related_papers": [],
            })

        if len(methods) <= 1:
            gaps.append({
                "category": "methodology",
                "description": "Limited methodological diversity. Consider exploring alternative approaches.",
                "confidence": 0.7,
                "related_papers": [p.get("title", "") for p in papers],
            })

        if not evaluations:
            gaps.append({
                "category": "evaluation",
                "description": "Evaluation metrics may be underreported. Consider standardizing benchmarks.",
                "confidence": 0.6,
                "related_papers": [],
            })

        return gaps


def gap_analyzer_node(state: dict[str, Any]) -> dict[str, Any]:
    findings = state.get("task_findings", {})
    papers = []
    for task_id, task_data in findings.items():
        if isinstance(task_data, dict):
            for provider, provider_data in task_data.items():
                if isinstance(provider_data, dict):
                    for item in provider_data.get("items", []):
                        if isinstance(item, dict):
                            papers.append(item)

    analyzer = GapAnalyzer()
    gaps = analyzer.analyze(papers)
    return {"gap_analysis": gaps}
