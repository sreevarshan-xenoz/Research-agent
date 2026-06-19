import pytest
from research_agent.output.grant_proposal import GrantProposalGenerator, generate_grant_proposal


def test_default_agency():
    gen = GrantProposalGenerator()
    assert gen.agency == "nsf"


def test_invalid_agency():
    with pytest.raises(ValueError, match="Unknown agency"):
        GrantProposalGenerator("fake")


def test_generate_basic():
    result = generate_grant_proposal(
        title="AI Research",
        pi_name="Dr. Smith",
        pi_institution="MIT",
        abstract="This project advances AI.",
        agency="nsf",
    )
    assert "National Science Foundation" in result
    assert "AI Research" in result
    assert "Dr. Smith" in result
    assert "This project advances AI." in result
    assert "Project Description" in result
    assert "Data Management Plan" in result


def test_generate_nih():
    result = generate_grant_proposal(
        title="Cancer Research",
        pi_name="Dr. Jones",
        pi_institution="JHU",
        abstract="Study cancer pathways.",
        agency="nih",
    )
    assert "National Institutes of Health" in result
    assert "Specific Aims" in result
    assert "Research Strategy" in result


def test_generate_erc():
    result = generate_grant_proposal(
        title="Frontier Physics",
        pi_name="Dr. Lee",
        pi_institution="CERN",
        abstract="Exploring fundamental forces.",
        agency="erc",
    )
    assert "European Research Council" in result
    assert "Extended Synopsis" in result


def test_with_papers():
    papers = [
        {"title": "Prior Work", "authors": "Smith et al.", "year": 2023, "journal": "Nature"},
    ]
    result = generate_grant_proposal(
        title="Continuing Research",
        pi_name="Dr. Smith",
        pi_institution="MIT",
        abstract="Building on prior work.",
        agency="nsf",
        papers=papers,
    )
    assert "Smith et al." in result
    assert "Prior Work" in result
