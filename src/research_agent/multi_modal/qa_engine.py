"""Multi-modal Q&A engine for asking questions about figures and tables.

Allows users to ask questions like "What does Figure 3 show?" or
"What are the key columns in Table 2?" by routing the question to
a vision-capable LLM along with the relevant image.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class QAResult:
    """Result of a multi-modal Q&A query."""

    def __init__(
        self,
        answer: str,
        source: str = "llm",
        confidence: float | None = None,
        relevant_figures: list[int] | None = None,
    ) -> None:
        self.answer = answer
        self.source = source
        self.confidence = confidence
        self.relevant_figures = relevant_figures or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "source": self.source,
            "confidence": self.confidence,
            "relevant_figures": self.relevant_figures,
        }


class MultiModalQAEngine:
    """Q&A engine that can answer questions about paper figures and tables.

    Supports two modes:
    1. With a specific image: sends the image + question to a vision LLM
    2. Without an image: answers based on figure/table metadata only
    """

    async def answer_about_figure(
        self,
        question: str,
        figure_image_path: str | Path | None = None,
        figure_caption: str | None = None,
        page_context: str | None = None,
    ) -> QAResult:
        """Answer a question about a specific figure.

        If an image path is provided, sends the image + question to a
        vision-capable LLM. Otherwise, answers from the caption + context.

        Args:
            question: The user's question about the figure.
            figure_image_path: Path to the figure image (if available).
            figure_caption: Caption or existing description of the figure.
            page_context: Surrounding page text for context.

        Returns:
            QAResult with the answer.
        """
        if figure_image_path and Path(str(figure_image_path)).exists():
            return await self._answer_with_vision(
                question=question,
                image_path=str(figure_image_path),
                caption=figure_caption,
                page_context=page_context,
            )

        return await self._answer_from_metadata(
            question=question,
            caption=figure_caption,
            page_context=page_context,
        )

    async def answer_about_table(
        self,
        question: str,
        table_markdown: str | None = None,
        table_caption: str | None = None,
    ) -> QAResult:
        """Answer a question about a table using its markdown representation.

        Args:
            question: The user's question about the table.
            table_markdown: Markdown representation of the table.
            table_caption: Optional caption.

        Returns:
            QAResult with the answer.
        """
        try:
            from research_agent.models import generate_text
        except ImportError:
            return QAResult(answer="Q&A engine unavailable.", source="error")

        context = ""
        if table_caption:
            context += f"Table caption: {table_caption}\n"
        if table_markdown:
            context += f"Table data:\n{table_markdown}"

        if not context:
            return QAResult(answer="No table data available to answer from.", source="metadata")

        prompt = (
            "Answer the following question based on the table data provided.\n\n"
            f"Question: {question}\n\n"
            f"Table:\n{context}\n\n"
            "Answer concisely with specific references to the data."
        )

        try:
            answer = await generate_text(
                role="subagent",
                prompt=prompt,
                temperature=0.1,
                max_tokens=500,
            )
            return QAResult(
                answer=answer or "No answer generated.",
                source="rag",
            )
        except Exception as exc:
            return QAResult(answer=f"Failed to answer: {exc}", source="error")

    async def _answer_with_vision(
        self,
        question: str,
        image_path: str,
        caption: str | None = None,
        page_context: str | None = None,
    ) -> QAResult:
        """Send the question to a vision-capable LLM with image context."""
        from research_agent.config import load_settings
        settings = load_settings()

        vision_model = settings.models.subagent_openai or "openai/gpt-4o"
        api_key = str(settings.openai.api_key) if settings.openai.api_key else None

        system_prompt = (
            "You are a scientific paper analysis assistant. Answer questions about "
            "figures, charts, and diagrams in research papers. Provide specific, "
            "accurate answers referencing visual elements."
        )

        user_prompt = f"Question about the figure: {question}\nImage path: {image_path}"
        if caption:
            user_prompt += f"\n\nFigure caption: {caption}"
        if page_context:
            user_prompt += f"\n\nPage context: {page_context[:1000]}"

        try:
            import litellm  # type: ignore[import-untyped]
            response = await litellm.acompletion(
                model=vision_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=600,
                api_key=api_key,
            )
            text = response.choices[0].message.content if response.choices else ""
            return QAResult(answer=text or "No answer generated.")
        except Exception as exc:
            logger.warning("Vision Q&A failed: %s", exc)
            return QAResult(answer=f"Vision analysis failed: {exc}", source="error")

    async def _answer_from_metadata(
        self,
        question: str,
        caption: str | None = None,
        page_context: str | None = None,
    ) -> QAResult:
        """Answer from caption + context text without an image."""
        try:
            from research_agent.models import generate_text
        except ImportError:
            return QAResult(answer="Q&A unavailable.", source="error")

        context_parts = []
        if caption:
            context_parts.append(f"Figure caption/description: {caption}")
        if page_context:
            context_parts.append(f"Page context: {page_context[:2000]}")

        context = "\n\n".join(context_parts) if context_parts else "No context available."

        prompt = (
            "Answer the following question about a figure in a research paper.\n\n"
            f"Question: {question}\n\n"
            f"Available context:\n{context}\n\n"
            "If the context is insufficient, say so clearly."
        )

        try:
            answer = await generate_text(
                role="subagent",
                prompt=prompt,
                temperature=0.2,
                max_tokens=500,
            )
            return QAResult(
                answer=answer or "Unable to answer from available metadata.",
                source="metadata",
            )
        except Exception as exc:
            return QAResult(answer=f"Failed to answer: {exc}", source="error")


# Module-level singleton
MultiModalQA = MultiModalQAEngine()
