from unittest.mock import patch

import pytest

from app.llm.openai_llm_client import OpenAILLMClient
from app.models.entry import Entry
from app.models.entry_tags import EntryTags


def _make_entry(entry_id: str, timestamp: str, text: str, tags: EntryTags | None = None) -> Entry:
    return Entry(user_id="u1", entry_id=entry_id, timestamp=timestamp, entry=text, tags=tags)


@pytest.fixture
def mock_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with patch("app.llm.openai_llm_client.OpenAI") as m:
        yield m.return_value


@pytest.fixture
def client(mock_openai) -> OpenAILLMClient:
    return OpenAILLMClient()


def test_answer_question_empty_entries_returns_fallback(client) -> None:
    result = client.answer_question([], "anything?")

    assert result == "I don't have any journal entries to answer that question."


def test_answer_question_entry_without_tags(client, mock_openai) -> None:
    mock_openai.chat.completions.create.return_value.choices[0].message.content = "answer"
    entry = _make_entry("e1", "2024-01-15T10:00:00", "I went hiking.")

    client.answer_question([entry], "What did I do?")

    _, kwargs = mock_openai.chat.completions.create.call_args
    user_content = kwargs["messages"][1]["content"]
    assert "[2024-01-15]\nI went hiking." in user_content
    assert "Topics:" not in user_content


def test_answer_question_entry_with_all_tags(client, mock_openai) -> None:
    mock_openai.chat.completions.create.return_value.choices[0].message.content = "answer"
    tags = EntryTags(topics=["hiking"], people=["Alice"], mood="happy", locations=["mountains"])
    entry = _make_entry("e1", "2024-01-15T10:00:00", "I went hiking.", tags)

    client.answer_question([entry], "What did I do?")

    _, kwargs = mock_openai.chat.completions.create.call_args
    user_content = kwargs["messages"][1]["content"]
    assert "Topics: hiking" in user_content
    assert "People: Alice" in user_content
    assert "Mood: happy" in user_content
    assert "Location: mountains" in user_content
    assert "I went hiking." in user_content


def test_answer_question_entry_with_partial_tags(client, mock_openai) -> None:
    mock_openai.chat.completions.create.return_value.choices[0].message.content = "answer"
    tags = EntryTags(mood="tired")
    entry = _make_entry("e1", "2024-01-15T10:00:00", "Long day.", tags)

    client.answer_question([entry], "How was my day?")

    _, kwargs = mock_openai.chat.completions.create.call_args
    user_content = kwargs["messages"][1]["content"]
    assert "Mood: tired" in user_content
    assert "Topics:" not in user_content
    assert "People:" not in user_content
    assert "Location:" not in user_content


def test_answer_question_entries_sorted_by_timestamp(client, mock_openai) -> None:
    mock_openai.chat.completions.create.return_value.choices[0].message.content = "answer"
    earlier = _make_entry("e1", "2024-01-10T10:00:00", "First entry.")
    later = _make_entry("e2", "2024-01-15T10:00:00", "Second entry.")

    client.answer_question([later, earlier], "order?")

    _, kwargs = mock_openai.chat.completions.create.call_args
    user_content = kwargs["messages"][1]["content"]
    assert user_content.index("First entry.") < user_content.index("Second entry.")


def test_answer_question_returns_llm_response(client, mock_openai) -> None:
    mock_openai.chat.completions.create.return_value.choices[0].message.content = "You went hiking."
    entry = _make_entry("e1", "2024-01-15T10:00:00", "I went hiking.")

    result = client.answer_question([entry], "What did I do?")

    assert result == "You went hiking."
