from __future__ import annotations

from typing import Any


AGENCY_TEMPLATES = {
    "nsf": {
        "name": "National Science Foundation",
        "sections": [
            "Cover Sheet",
            "Project Summary",
            "Table of Contents",
            "Project Description",
            "References Cited",
            "Biographical Sketches",
            "Budget & Justification",
            "Current & Pending Support",
            "Facilities, Equipment & Other Resources",
            "Data Management Plan",
            "Mentoring Plan",
        ],
    },
    "nih": {
        "name": "National Institutes of Health",
        "sections": [
            "Face Page",
            "Abstract",
            "Project Narrative",
            "Specific Aims",
            "Research Strategy",
            "Bibliography & References Cited",
            "Protection of Human Subjects",
            "Vertebrate Animals",
            "Select Agent Research",
            "Budget & Justification",
            "Biographical Sketch",
            "Resources",
        ],
    },
    "erc": {
        "name": "European Research Council",
        "sections": [
            "Title Page",
            "Extended Synopsis",
            "Scientific Proposal",
            "Curriculum Vitae",
            "Funding ID",
            "Ethics Issues",
        ],
    },
}


class GrantProposalGenerator:
    def __init__(self, agency: str = "nsf"):
        self.agency = agency.lower()
        template = AGENCY_TEMPLATES.get(self.agency)
        if template is None:
            raise ValueError(f"Unknown agency '{agency}'. Choose from: {', '.join(AGENCY_TEMPLATES)}")
        self.template = template

    def generate(
        self,
        title: str,
        pi_name: str,
        pi_institution: str,
        abstract: str,
        papers: list[dict[str, Any]] | None = None,
        budget: str | None = None,
        duration: str = "3 years",
    ) -> str:
        papers = papers or []
        budget = budget or "TBD"

        lines = [
            f"# {self.template['name']} Grant Proposal",
            f"**Agency:** {self.template['name']}",
            f"**Duration:** {duration}",
            "",
            "---",
            "",
        ]

        for section in self.template["sections"]:
            lines.append(f"## {section}")
            lines.append(self._generate_section(section, title, pi_name, pi_institution, abstract, papers, budget))
            lines.append("")

        return "\n".join(lines)

    def _generate_section(
        self,
        section: str,
        title: str,
        pi_name: str,
        pi_institution: str,
        abstract: str,
        papers: list[dict[str, Any]],
        budget: str,
    ) -> str:
        section_lower = section.lower()

        if "cover" in section_lower or "face" in section_lower or "title" in section_lower:
            return f"\n**Title:** {title}\n**PI:** {pi_name}, {pi_institution}\n**Agency:** {self.template['name']}\n"

        if "abstract" in section_lower or "summary" in section_lower or "synopsis" in section_lower:
            return f"\n{abstract}\n"

        if "references" in section_lower or "bibliography" in section_lower:
            if papers:
                refs = "\n".join(
                    f"{i+1}. {p.get('authors', 'Unknown')} ({p.get('year', 'n.d.')}). "
                    f"{p.get('title', 'Untitled')}. {p.get('journal', '')}."
                    for i, p in enumerate(papers[:10])
                )
                return f"\n{refs}\n"
            return "\nReferences to be added.\n"

        if "budget" in section_lower:
            return f"\n{budget}\n"

        if "data management" in section_lower:
            return (
                "\nData will be stored and shared according to open science best practices. "
                "All code and datasets will be made publicly available via GitHub and Zenodo. "
                "A Data Management Plan will be finalized within 60 days of award.\n"
            )

        if "mentoring" in section_lower or "biographical" in section_lower:
            return f"\nTo be provided by {pi_name} ({pi_institution}).\n"

        if "ethics" in section_lower:
            return "\nNo ethical issues identified. All research will be conducted in accordance with institutional guidelines.\n"

        return "\nContent to be developed.\n"


def generate_grant_proposal(
    title: str,
    pi_name: str,
    pi_institution: str,
    abstract: str,
    papers: list[dict[str, Any]] | None = None,
    agency: str = "nsf",
    budget: str | None = None,
) -> str:
    generator = GrantProposalGenerator(agency)
    return generator.generate(
        title=title,
        pi_name=pi_name,
        pi_institution=pi_institution,
        abstract=abstract,
        papers=papers,
        budget=budget,
    )
