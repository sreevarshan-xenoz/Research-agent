import pytest
from research_agent.orchestration.nodes.gap_analyzer import GapAnalyzer

def test_gap_analyzer_empty():
    analyzer = GapAnalyzer()
    gaps = analyzer.analyze([])
    assert gaps == []

def test_gap_analyzer_with_papers():
    analyzer = GapAnalyzer()
    papers = [
        {"title": "Paper A", "abstract": "We used CNNs for classification", "method": "CNN"},
        {"title": "Paper B", "abstract": "We used RNNs for classification", "method": "RNN"},
    ]
    gaps = analyzer.analyze(papers)
    assert isinstance(gaps, list)
