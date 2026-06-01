import pytest
from pathlib import Path
from research_agent.output.blog_generator import (
    extract_sections_from_latex,
    generate_all,
    generate_blog_post,
    generate_newsletter,
    generate_twitter_thread,
)

SAMPLE_TEX = r"""
\title{Attention Is All You Need}
\maketitle
\begin{abstract}
We propose a new network architecture, the Transformer.
\end{abstract}
\section{Introduction}
The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.
\section{Methodology}
Our model uses multi-head self-attention.
\section{Results}
The Transformer outperforms all previous models.
"""

def test_extract_sections_from_latex():
    sections = extract_sections_from_latex(SAMPLE_TEX)
    assert "abstract" in sections
    assert "introduction" in sections
    assert "methodology" in sections
    assert "results" in sections
    assert "Transformer" in sections["abstract"]
    assert "multi-head self-attention" in sections["methodology"]

def test_generate_blog_post():
    sections = {"title": "Test Title", "abstract": "Test abstract.", "introduction": "Intro content."}
    blog = generate_blog_post(sections, "test")
    assert "# Test Title" in blog
    assert "## TL;DR" in blog
    assert "Test abstract." in blog
    assert "## Introduction" in blog
    assert "Intro content." in blog

def test_generate_newsletter():
    sections = {"abstract": "A" * 300, "results": "Key result."}
    nl = generate_newsletter(sections)
    assert "**In Brief**" in nl
    assert "**Key Finding**" in nl
    assert "..." in nl

def test_generate_twitter_thread():
    sections = {"title": "My Paper", "abstract": "Important work."}
    thread = generate_twitter_thread(sections)
    assert len(thread) >= 2
    assert thread[0].startswith("\U0001f9f5")
    assert thread[1].startswith("\U0001f4c4")

def test_generate_all():
    tex = r"\title{T}\begin{abstract}A\end{abstract}\section{Intro}I\end{section}"
    result = generate_all(tex, "test", formats=["blog"])
    assert "blog" in result
    assert "newsletter" not in result
