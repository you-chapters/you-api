from unittest.mock import MagicMock, call, patch

import app.handler_embedding as handler_module
from app.models.entry_tags import EntryTags

_VECTOR = [0.1] * 1536
_TAGS = EntryTags(topics=["work"], mood="positive", people=["Alice Smith"], locations=["NYC"])

_INSERT_RECORD = {
    "eventName": "INSERT",
    "dynamodb": {
        "NewImage": {
            "entry_id": {"S": "entry-123"},
            "user_id": {"S": "user-1"},
            "timestamp": {"S": "2024-01-15T10:00:00+00:00"},
            "entry": {"S": "Today was a good day"},
        }
    },
}

_INSERT_RECORD_WITH_LOCATION = {
    "eventName": "INSERT",
    "dynamodb": {
        "NewImage": {
            "entry_id": {"S": "entry-123"},
            "user_id": {"S": "user-1"},
            "timestamp": {"S": "2024-01-15T10:00:00+00:00"},
            "entry": {"S": "Today was a good day"},
            "location": {"S": "New York"},
        }
    },
}


def _make_event(*records: dict) -> dict:
    return {"Records": list(records)}


def _patched_handler(event, mock_embed_return=_VECTOR, mock_tags=None):
    if mock_tags is None:
        mock_tags = EntryTags()
    mock_port = MagicMock()
    mock_port.embed.return_value = mock_embed_return
    mock_repo = MagicMock()
    mock_tag_port = MagicMock()
    mock_tag_port.extract.return_value = mock_tags
    mock_table = MagicMock()
    with patch.object(handler_module, "_embedding_port", return_value=mock_port), \
         patch.object(handler_module, "_vector_repository", return_value=mock_repo), \
         patch.object(handler_module, "_tag_extraction_client", return_value=mock_tag_port), \
         patch.object(handler_module, "_dynamodb_table", return_value=mock_table):
        handler_module.handler(event, None)
    return mock_port, mock_repo, mock_tag_port, mock_table


def test_handler_processes_insert_record() -> None:
    mock_port, mock_repo, mock_tag_port, mock_table = _patched_handler(_make_event(_INSERT_RECORD))

    mock_port.embed.assert_called_once()
    tags = mock_tag_port.extract.return_value
    mock_repo.upsert.assert_called_once_with("entry-123", "user-1", _VECTOR, 1705312800, tags)


def test_handler_embed_text_includes_date_and_entry() -> None:
    mock_port, *_ = _patched_handler(_make_event(_INSERT_RECORD))

    call_text = mock_port.embed.call_args[0][0]
    assert "2024-01-15T10:00:00+00:00" in call_text
    assert "Today was a good day" in call_text


def test_handler_embed_text_includes_tags() -> None:
    mock_port, *_ = _patched_handler(_make_event(_INSERT_RECORD), mock_tags=_TAGS)

    call_text = mock_port.embed.call_args[0][0]
    assert "work" in call_text
    assert "positive" in call_text
    assert "Alice Smith" in call_text
    assert "NYC" in call_text


def test_handler_extracts_tags_with_correct_args() -> None:
    *_, mock_tag_port, _ = _patched_handler(_make_event(_INSERT_RECORD))

    mock_tag_port.extract.assert_called_once_with("Today was a good day", "2024-01-15T10:00:00+00:00", None)


def test_handler_passes_location_to_tag_extraction() -> None:
    *_, mock_tag_port, _ = _patched_handler(_make_event(_INSERT_RECORD_WITH_LOCATION))

    mock_tag_port.extract.assert_called_once_with("Today was a good day", "2024-01-15T10:00:00+00:00", "New York")


def test_handler_writes_tags_back_to_dynamodb() -> None:
    *_, mock_tag_port, mock_table = _patched_handler(_make_event(_INSERT_RECORD), mock_tags=_TAGS)

    mock_table.update_item.assert_called_once_with(
        Key={"user_id": "user-1", "entry_id": "entry-123"},
        UpdateExpression="SET tags = :tags",
        ExpressionAttributeValues={":tags": _TAGS.model_dump()},
    )


def test_handler_skips_non_insert_records() -> None:
    modify_record = {**_INSERT_RECORD, "eventName": "MODIFY"}
    remove_record = {**_INSERT_RECORD, "eventName": "REMOVE"}

    for record in (modify_record, remove_record):
        mock_port, mock_repo, mock_tag_port, mock_table = _patched_handler(_make_event(record))
        mock_port.embed.assert_not_called()
        mock_repo.upsert.assert_not_called()
        mock_tag_port.extract.assert_not_called()
        mock_table.update_item.assert_not_called()


def test_handler_processes_empty_event() -> None:
    mock_port, mock_repo, mock_tag_port, mock_table = _patched_handler({"Records": []})
    mock_port.embed.assert_not_called()
    mock_repo.upsert.assert_not_called()
    mock_tag_port.extract.assert_not_called()
    mock_table.update_item.assert_not_called()


def test_handler_processes_multiple_insert_records() -> None:
    record2 = {
        "eventName": "INSERT",
        "dynamodb": {
            "NewImage": {
                "entry_id": {"S": "entry-456"},
                "user_id": {"S": "user-2"},
                "timestamp": {"S": "2024-01-16T12:00:00+00:00"},
                "entry": {"S": "Another entry"},
            }
        },
    }

    mock_port, mock_repo, mock_tag_port, mock_table = _patched_handler(_make_event(_INSERT_RECORD, record2))

    assert mock_port.embed.call_count == 2
    assert mock_repo.upsert.call_count == 2
    assert mock_tag_port.extract.call_count == 2
    assert mock_table.update_item.call_count == 2


def test_handler_skips_non_insert_but_processes_insert_in_mixed_batch() -> None:
    modify_record = {**_INSERT_RECORD, "eventName": "MODIFY"}

    mock_port, mock_repo, mock_tag_port, mock_table = _patched_handler(_make_event(modify_record, _INSERT_RECORD))

    mock_port.embed.assert_called_once()
    mock_repo.upsert.assert_called_once()
    mock_tag_port.extract.assert_called_once()
    mock_table.update_item.assert_called_once()
