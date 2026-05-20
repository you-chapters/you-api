import json
from unittest.mock import MagicMock, patch

import pytest

from app.models.entry_tags import EntryTags
from app.tag_extraction.openai_tag_extraction_client import OpenAITagExtractionClient


@pytest.fixture
def client(monkeypatch) -> OpenAITagExtractionClient:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    with patch("app.tag_extraction.openai_tag_extraction_client.OpenAI"):
        return OpenAITagExtractionClient()


def _mock_response(data: dict, client: OpenAITagExtractionClient) -> None:
    msg = MagicMock()
    msg.content = json.dumps(data)
    client._client.chat.completions.create.return_value.choices = [MagicMock(message=msg)]


def test_extract_parses_full_response(client: OpenAITagExtractionClient) -> None:
    _mock_response(
        {"people": ["Alice Smith"], "locations": ["NYC"], "topics": ["work"], "mood": "positive", "time_markers": []},
        client,
    )

    result = client.extract("Had a meeting with Alice in NYC.", "2024-01-15T10:00:00+00:00", None)

    assert result == EntryTags(people=["Alice Smith"], locations=["NYC"], topics=["work"], mood="positive")


def test_extract_passes_location_in_prompt(client: OpenAITagExtractionClient) -> None:
    _mock_response({"people": [], "locations": [], "topics": [], "mood": None, "time_markers": []}, client)

    client.extract("Some text", "2024-01-15T10:00:00+00:00", "Berlin")

    call_args = client._client.chat.completions.create.call_args
    user_message = call_args.kwargs["messages"][1]["content"]
    assert "Berlin" in user_message


def test_extract_omits_location_from_prompt_when_none(client: OpenAITagExtractionClient) -> None:
    _mock_response({"people": [], "locations": [], "topics": [], "mood": None, "time_markers": []}, client)

    client.extract("Some text", "2024-01-15T10:00:00+00:00", None)

    call_args = client._client.chat.completions.create.call_args
    user_message = call_args.kwargs["messages"][1]["content"]
    assert "User location" not in user_message


def test_extract_uses_json_response_format(client: OpenAITagExtractionClient) -> None:
    _mock_response({"people": [], "locations": [], "topics": [], "mood": None, "time_markers": []}, client)

    client.extract("text", "2024-01-15T10:00:00+00:00", None)

    call_args = client._client.chat.completions.create.call_args
    assert call_args.kwargs["response_format"] == {"type": "json_object"}


def test_extract_ignores_extra_fields_in_response(client: OpenAITagExtractionClient) -> None:
    _mock_response(
        {"people": [], "locations": [], "topics": [], "mood": None, "time_markers": [], "unexpected_field": "value"},
        client,
    )

    result = client.extract("text", "2024-01-15T10:00:00+00:00", None)

    assert result == EntryTags()


def test_extract_handles_partial_response(client: OpenAITagExtractionClient) -> None:
    _mock_response({"topics": ["family"], "mood": "neutral"}, client)

    result = client.extract("text", "2024-01-15T10:00:00+00:00", None)

    assert result.topics == ["family"]
    assert result.mood == "neutral"
    assert result.people == []
