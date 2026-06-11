from unittest.mock import patch

import pytest

from app.models.entry import Entry
from app.repositories.dynamodb_entry_repository import DynamoDBEntryRepository


def _item(**kwargs) -> dict:
    d = {"user_id": "u1", "entry_id": "e1", "entry": "hello", "timestamp": "2024-01-01T00:00:00"}
    d.update(kwargs)
    return d


@pytest.fixture
def mock_resource():
    with patch("app.repositories.dynamodb_entry_repository.boto3.resource") as m:
        m.return_value.Table.return_value.name = "test-table"
        yield m.return_value


@pytest.fixture
def repo(mock_resource) -> DynamoDBEntryRepository:
    return DynamoDBEntryRepository("test-table")


def test_save_calls_put_item(repo, mock_resource) -> None:
    entry = Entry(**_item())

    repo.save(entry)

    mock_resource.Table.return_value.put_item.assert_called_once_with(Item=entry.model_dump())


def test_get_returns_entry_when_found(repo, mock_resource) -> None:
    item = _item()
    mock_resource.Table.return_value.get_item.return_value = {"Item": item}

    result = repo.get("u1", "e1")

    assert result == Entry(**item)


def test_get_returns_none_when_not_found(repo, mock_resource) -> None:
    mock_resource.Table.return_value.get_item.return_value = {}

    assert repo.get("u1", "missing") is None


def test_list_by_user_returns_entries(repo, mock_resource) -> None:
    items = [_item(entry_id="e1"), _item(entry_id="e2")]
    mock_resource.Table.return_value.query.return_value = {"Items": items}

    result = repo.list_by_user("u1")

    assert len(result) == 2
    assert all(isinstance(e, Entry) for e in result)


def test_get_many_returns_empty_for_no_ids(repo, mock_resource) -> None:
    result = repo.get_many("u1", [])

    assert result == []
    mock_resource.batch_get_item.assert_not_called()


def test_get_many_returns_entries(repo, mock_resource) -> None:
    items = [_item(entry_id="e1"), _item(entry_id="e2")]
    mock_resource.batch_get_item.return_value = {"Responses": {"test-table": items}}

    result = repo.get_many("u1", ["e1", "e2"])

    assert len(result) == 2
    assert all(isinstance(e, Entry) for e in result)


def test_list_by_day_queries_past_10_years(repo, mock_resource) -> None:
    from unittest.mock import call, patch
    from datetime import datetime, timezone
    fixed = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
    mock_resource.Table.return_value.query.return_value = {"Items": []}

    with patch("app.repositories.dynamodb_entry_repository.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        repo.list_by_day("u1", 6, 11)

    assert mock_resource.Table.return_value.query.call_count == 10


def test_list_by_day_returns_entries_sorted_newest_first(repo, mock_resource) -> None:
    from unittest.mock import patch
    from datetime import datetime, timezone
    fixed = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
    items_2024 = [_item(entry_id="e1", timestamp="2024-06-11T10:00:00")]
    items_2023 = [_item(entry_id="e2", timestamp="2023-06-11T08:00:00")]
    mock_resource.Table.return_value.query.side_effect = [
        {"Items": items_2024},
        {"Items": items_2023},
        *[{"Items": []} for _ in range(8)],
    ]

    with patch("app.repositories.dynamodb_entry_repository.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        result = repo.list_by_day("u1", 6, 11)

    assert result[0].entry_id == "e1"
    assert result[1].entry_id == "e2"


def test_list_by_day_skips_invalid_dates(repo, mock_resource) -> None:
    from unittest.mock import patch
    from datetime import datetime, timezone
    fixed = datetime(2024, 2, 29, 12, 0, 0, tzinfo=timezone.utc)
    mock_resource.Table.return_value.query.return_value = {"Items": []}

    with patch("app.repositories.dynamodb_entry_repository.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        result = repo.list_by_day("u1", 2, 29)

    assert isinstance(result, list)
    assert mock_resource.Table.return_value.query.call_count < 10


def test_list_by_day_uses_user_timestamp_index(repo, mock_resource) -> None:
    from unittest.mock import patch
    from datetime import datetime, timezone
    fixed = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)
    mock_resource.Table.return_value.query.return_value = {"Items": []}

    with patch("app.repositories.dynamodb_entry_repository.datetime") as mock_dt:
        mock_dt.now.return_value = fixed
        repo.list_by_day("u1", 6, 11)

    call_kwargs = mock_resource.Table.return_value.query.call_args_list[0][1]
    assert call_kwargs["IndexName"] == "user_timestamp_index"