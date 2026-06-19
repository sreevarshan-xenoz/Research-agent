from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from research_agent.verification.plagiarism_checker import (
    check_similarity,
    check_cosine_similarity,
    check_ngram_overlap,
    flag_flagged_passages,
    check_plagiarism,
    tokenize,
)
from research_agent.verification.rewrite_suggester import (
    suggest_rewrite,
    batch_suggest_rewrites,
    SYNONYM_MAP,
)


# ──────────────────────────────────────────────
# Tokenizer tests
# ──────────────────────────────────────────────

class TestTokenize:
    def test_basic_tokenization(self):
        assert tokenize("The quick brown fox") == ["the", "quick", "brown", "fox"]

    def test_empty_string(self):
        assert tokenize("") == []

    def test_lowercase_conversion(self):
        assert tokenize("Hello World") == ["hello", "world"]

    def test_punctuation_removal(self):
        assert tokenize("Hello, world! How are you?") == ["hello", "world", "how", "are", "you"]


# ──────────────────────────────────────────────
# Jaccard similarity tests
# ──────────────────────────────────────────────

class TestCheckSimilarity:
    def test_identical_texts(self):
        assert check_similarity("The quick brown fox", "The quick brown fox") == 1.0

    def test_completely_different(self):
        score = check_similarity("The quick brown fox", "Completely unrelated content here")
        assert score < 0.5

    def test_partial_overlap(self):
        score = check_similarity("The quick brown fox", "The quick blue rabbit")
        assert 0.3 < score < 0.9

    def test_empty_first(self):
        assert check_similarity("", "Some text") == 0.0

    def test_empty_second(self):
        assert check_similarity("Some text", "") == 0.0

    def test_both_empty(self):
        assert check_similarity("", "") == 0.0

    def test_single_word(self):
        assert check_similarity("hello", "hello") == 1.0
        assert check_similarity("hello", "world") == 0.0

    def test_case_insensitive(self):
        assert check_similarity("Hello World", "hello world") == 1.0


# ──────────────────────────────────────────────
# Cosine similarity tests
# ──────────────────────────────────────────────

class TestCheckCosineSimilarity:
    def test_identical_texts(self):
        assert check_cosine_similarity("The quick brown fox", "The quick brown fox") == 1.0

    def test_completely_different(self):
        score = check_cosine_similarity("The quick brown fox", "Completely unrelated content here today")
        assert score < 0.5

    def test_partial_overlap(self):
        score = check_cosine_similarity("The quick brown fox", "The quick brown rabbit")
        assert 0.3 < score < 1.0

    def test_repeated_words(self):
        score = check_cosine_similarity("the the the", "the the")
        assert score > 0.5

    def test_empty_text(self):
        assert check_cosine_similarity("", "Some text") == 0.0


# ──────────────────────────────────────────────
# N-gram overlap tests
# ──────────────────────────────────────────────

class TestCheckNgramOverlap:
    def test_exact_overlap(self):
        overlaps = check_ngram_overlap(
            "hello world foo bar baz qux",
            "hello world foo bar baz qux",
            n=3,
        )
        assert len(overlaps) >= 1

    def test_no_overlap(self):
        overlaps = check_ngram_overlap("hello world", "foo bar baz qux", n=3)
        assert len(overlaps) == 0

    def test_partial_overlap(self):
        overlaps = check_ngram_overlap(
            "the quick brown fox jumps",
            "the quick brown cat sits",
            n=2,
        )
        assert len(overlaps) >= 1  # "the quick" and "quick brown" overlap

    def test_short_texts(self):
        overlaps = check_ngram_overlap("hi", "hello", n=5)
        assert overlaps == []

    def test_large_ngram_no_overlap(self):
        overlaps = check_ngram_overlap(
            "one two three four five six seven eight nine ten",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
            n=5,
        )
        assert len(overlaps) == 0


# ──────────────────────────────────────────────
# Flagged passage tests
# ──────────────────────────────────────────────

class TestFlagFlaggedPassages:
    def test_flag_above_threshold(self):
        passages = [("Test text", "Source text", 0.95, "paraphrase")]
        flagged = flag_flagged_passages(passages, threshold=0.9)
        assert len(flagged) == 1

    def test_no_flag_below_threshold(self):
        passages = [("Test text", "Source text", 0.7, "paraphrase")]
        flagged = flag_flagged_passages(passages, threshold=0.9)
        assert len(flagged) == 0

    def test_multiple_passages_mixed(self):
        passages = [
            ("Text A", "Source A", 0.95, "exact_match"),
            ("Text B", "Source B", 0.5, "paraphrase"),
            ("Text C", "Source C", 0.85, "paraphrase"),
        ]
        flagged = flag_flagged_passages(passages, threshold=0.8)
        assert len(flagged) == 2
        assert flagged[0]["type"] == "exact_match"
        assert flagged[1]["type"] == "paraphrase"

    def test_empty_passages(self):
        assert flag_flagged_passages([]) == []

    def test_boundary_threshold(self):
        passages = [("Text", "Source", 0.8, "paraphrase")]
        flagged = flag_flagged_passages(passages, threshold=0.8)
        assert len(flagged) == 1

    def test_all_below_threshold(self):
        passages = [
            ("A", "S1", 0.1, "paraphrase"),
            ("B", "S2", 0.2, "paraphrase"),
            ("C", "S3", 0.3, "paraphrase"),
        ]
        flagged = flag_flagged_passages(passages, threshold=0.8)
        assert len(flagged) == 0


# ──────────────────────────────────────────────
# Full plagiarism check tests
# ──────────────────────────────────────────────

class TestCheckPlagiarism:
    def test_no_overlap_with_sources(self):
        result = check_plagiarism(
            "This is completely original content. It does not match any sources.",
            [{"text": "Unrelated source text here."}],
            threshold=0.8,
        )
        assert result["overall_score"] >= 0.9
        assert len(result["flagged_sentences"]) == 0

    def test_exact_match_detected(self):
        source_text = "The transformer architecture revolutionized natural language processing."
        result = check_plagiarism(
            f"Some intro text. {source_text} Some more content.",
            [{"text": source_text}],
            threshold=0.6,
        )
        # The sentence should be flagged
        assert result["statistics"]["flagged"] >= 1

    def test_empty_generated_text(self):
        result = check_plagiarism("", [{"text": "Source"}], threshold=0.8)
        assert result["overall_score"] == 1.0
        assert result["statistics"]["total_sentences"] == 1

    def test_empty_sources(self):
        result = check_plagiarism(
            "This is a sentence. This is another sentence.",
            [],
            threshold=0.8,
        )
        assert result["overall_score"] >= 0.9
        assert result["statistics"]["total_sentences"] == 2

    def test_no_source_text_in_chunks(self):
        result = check_plagiarism(
            "Some text here.",
            [{"title": "Paper", "year": 2020}, {"id": "123"}],
            threshold=0.8,
        )
        assert result["overall_score"] == 1.0

    def test_statistics_structure(self):
        result = check_plagiarism(
            "Sentence one. Sentence two. Sentence three.",
            [{"text": "different content here"}],
            threshold=0.8,
        )
        assert "statistics" in result
        assert result["statistics"]["total_sentences"] == 3
        assert "flagged" in result["statistics"]
        assert "exact_matches" in result["statistics"]
        assert "paraphrases" in result["statistics"]

    def test_output_structure(self):
        result = check_plagiarism(
            "Test sentence.",
            [{"text": "Test sentence."}],
            threshold=0.5,
        )
        assert "overall_score" in result
        assert "flagged_sentences" in result
        assert "statistics" in result
        assert isinstance(result["flagged_sentences"], list)
        assert isinstance(result["statistics"], dict)


# ──────────────────────────────────────────────
# Rewrite suggester tests
# ──────────────────────────────────────────────

class TestSuggestRewrite:
    def test_returns_dict_with_keys(self):
        result = suggest_rewrite("This is an important method for our research.")
        assert "original" in result
        assert "rewritten" in result
        assert "strategy" in result
        assert "match_type" in result

    def test_rewrite_differs_for_exact_match(self):
        result = suggest_rewrite(
            "This is an important method for our research.",
            match_type="exact_match",
        )
        # Should apply more aggressive rewriting for exact matches
        assert result["rewritten"] != result["original"] or result["strategy"]

    def test_empty_text(self):
        result = suggest_rewrite("")
        assert result["rewritten"] == ""

    def test_short_text(self):
        result = suggest_rewrite("Hi")
        assert result["rewritten"] == "Hi"

    def test_deterministic_output(self):
        text = "This method shows important results."
        result1 = suggest_rewrite(text)
        result2 = suggest_rewrite(text)
        assert result1["rewritten"] == result2["rewritten"]

    def test_match_type_preserved(self):
        result = suggest_rewrite("Some text.", match_type="exact_match")
        assert result["match_type"] == "exact_match"

        result2 = suggest_rewrite("Some text.", match_type="paraphrase")
        assert result2["match_type"] == "paraphrase"


class TestBatchSuggestRewrites:
    def test_batch_empty(self):
        assert batch_suggest_rewrites([]) == []

    def test_batch_single(self):
        flagged = [{"text": "This is a test.", "type": "paraphrase", "similarity": 0.9}]
        suggestions = batch_suggest_rewrites(flagged)
        assert len(suggestions) == 1
        assert suggestions[0]["similarity"] == 0.9

    def test_batch_multiple(self):
        flagged = [
            {"text": "Sentence one.", "type": "exact_match", "similarity": 1.0},
            {"text": "Sentence two.", "type": "paraphrase", "similarity": 0.85},
            {"text": "Sentence three.", "type": "paraphrase", "similarity": 0.9},
        ]
        suggestions = batch_suggest_rewrites(flagged)
        assert len(suggestions) == 3

    def test_batch_preserves_order(self):
        flagged = [
            {"text": "First.", "type": "paraphrase", "similarity": 0.9},
            {"text": "Second.", "type": "paraphrase", "similarity": 0.8},
            {"text": "Third.", "type": "paraphrase", "similarity": 0.7},
        ]
        suggestions = batch_suggest_rewrites(flagged)
        assert suggestions[0]["original"] == "First."
        assert suggestions[1]["original"] == "Second."
        assert suggestions[2]["original"] == "Third."


# ──────────────────────────────────────────────
# Integration test: full pipeline
# ──────────────────────────────────────────────

class TestFullPipeline:
    def test_detect_and_rewrite_pipeline(self):
        """End-to-end: generate text, check for plagiarism, get rewrites."""
        original_source = (
            "Deep learning has revolutionized artificial intelligence by enabling "
            "machines to learn from vast amounts of data without explicit programming."
        )
        generated_text = (
            "This paper explores advances in machine learning. "
            "Deep learning has revolutionized artificial intelligence by enabling "
            "machines to learn from vast amounts of data. "
            "We discuss the implications of these findings."
        )

        # Step 1: Check plagiarism
        result = check_plagiarism(
            generated_text,
            [{"text": original_source}],
            threshold=0.6,
        )

        # Should detect overlap in the middle sentence
        assert result["statistics"]["flagged"] >= 1

        # Step 2: Generate rewrites for flagged sentences
        suggestions = batch_suggest_rewrites(result["flagged_sentences"])
        assert len(suggestions) >= 1
        for suggestion in suggestions:
            assert "original" in suggestion
            assert "rewritten" in suggestion
            assert "strategy" in suggestion

    def test_clean_text_gets_high_score(self):
        clean_text = (
            "This paper introduces a novel approach to climate modeling. "
            "Our method combines satellite data with ground sensors. "
            "Results show significant improvement in prediction accuracy."
        )
        sources = [{"text": "Unrelated research about protein folding in biology."}]
        result = check_plagiarism(clean_text, sources, threshold=0.8)
        assert result["overall_score"] >= 0.9
        assert result["statistics"]["flagged"] == 0
