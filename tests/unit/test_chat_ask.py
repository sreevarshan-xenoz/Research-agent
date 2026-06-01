import pytest
from research_agent.chat.ask import answer_question

@pytest.mark.asyncio
async def test_answer_question_empty_library():
    result = await answer_question("nonexistent_lib", "test question")
    assert "answer" in result
    assert "citations" in result
