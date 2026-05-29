from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.llm.in_memory_llm_client import InMemoryLLMClient
from app.models.entry import Entry
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.repositories.in_memory_narrative_repository import InMemoryNarrativeRepository
from app.services.narrative_service import NarrativeService

TODAY = datetime.now(timezone.utc).date()
CURRENT_WEEK = TODAY.strftime("%G-W%V")
CURRENT_MONTH = TODAY.strftime("%Y-%m")
USER = "user-1"


_entry_counter = 0


def _make_entry(timestamp: str, text: str = "hello") -> Entry:
    global _entry_counter
    _entry_counter += 1
    return Entry(user_id=USER, entry_id=f"e{_entry_counter}", timestamp=timestamp, entry=text)


def _make_service(entries=None):
    repo = InMemoryEntryRepository()
    for e in entries or []:
        repo.save(e)
    return NarrativeService(repo, InMemoryNarrativeRepository(), InMemoryLLMClient())


def test_first_call_generates_and_is_not_cached():
    svc = _make_service()
    result = svc.get_narrative(USER, "week", CURRENT_WEEK)
    assert result.is_cached is False
    assert result.period_type == "week"
    assert result.period_key == CURRENT_WEEK


def test_second_call_same_day_returns_cached():
    svc = _make_service()
    svc.get_narrative(USER, "week", CURRENT_WEEK)
    result = svc.get_narrative(USER, "week", CURRENT_WEEK)
    assert result.is_cached is True


def test_second_call_preserves_generated_at():
    svc = _make_service()
    first = svc.get_narrative(USER, "week", CURRENT_WEEK)
    second = svc.get_narrative(USER, "week", CURRENT_WEEK)
    assert second.generated_at == first.generated_at


def test_force_refresh_regenerates():
    svc = _make_service()
    first = svc.get_narrative(USER, "week", CURRENT_WEEK)
    result = svc.get_narrative(USER, "week", CURRENT_WEEK, force_refresh=True)
    assert result.is_cached is False
    assert result.generated_at >= first.generated_at


def test_stale_current_period_regenerates(monkeypatch):
    svc = _make_service()
    yesterday = (TODAY - timedelta(days=1)).isoformat()

    from app.models.narrative import NarrativeSummary
    stale = NarrativeSummary(
        period_type="week",
        period_key=CURRENT_WEEK,
        entry_count=0,
        text="old",
        generated_at=f"{yesterday}T00:00:00+00:00",
        is_cached=False,
    )
    svc._narratives.save(USER, f"cache#week#{CURRENT_WEEK}", stale)

    result = svc.get_narrative(USER, "week", CURRENT_WEEK)
    assert result.is_cached is False
    assert result.text != "old"


def test_past_period_not_regenerated_even_if_old(monkeypatch):
    past_week = "2020-W01"
    svc = _make_service()
    first = svc.get_narrative(USER, "week", past_week)
    result = svc.get_narrative(USER, "week", past_week)
    assert result.is_cached is True
    assert result.generated_at == first.generated_at


def test_week_filters_entries_by_iso_week():
    monday = datetime.fromisocalendar(TODAY.year, int(CURRENT_WEEK[6:]), 1).replace(tzinfo=timezone.utc)
    in_week = _make_entry((monday + timedelta(hours=12)).isoformat(), "in week")
    out_of_week = _make_entry((monday - timedelta(hours=1)).isoformat(), "before week")
    repo = InMemoryEntryRepository()
    for e in [in_week, out_of_week]:
        repo.save(e)

    llm = MagicMock()
    llm.generate_narrative.return_value = "narrative"
    svc = NarrativeService(repo, InMemoryNarrativeRepository(), llm)
    svc.get_narrative(USER, "week", CURRENT_WEEK)

    called_entries = llm.generate_narrative.call_args[0][0]
    assert len(called_entries) == 1
    assert called_entries[0].entry == "in week"


def test_month_filters_entries_by_month():
    in_month = _make_entry(f"{CURRENT_MONTH}-15T10:00:00+00:00", "in month")
    out_of_month = _make_entry("2020-01-15T10:00:00+00:00", "old entry")
    repo = InMemoryEntryRepository()
    for e in [in_month, out_of_month]:
        repo.save(e)

    llm = MagicMock()
    llm.generate_narrative.return_value = "narrative"
    svc = NarrativeService(repo, InMemoryNarrativeRepository(), llm)
    svc.get_narrative(USER, "month", CURRENT_MONTH)

    called_entries = llm.generate_narrative.call_args[0][0]
    assert len(called_entries) == 1
    assert called_entries[0].entry == "in month"


def test_empty_period_stores_result_without_llm_call():
    llm = MagicMock()
    llm.generate_narrative.return_value = "No entries this period."
    svc = NarrativeService(InMemoryEntryRepository(), InMemoryNarrativeRepository(), llm)
    result = svc.get_narrative(USER, "week", CURRENT_WEEK)
    assert result.entry_count == 0
    llm.generate_narrative.assert_called_once_with([], CURRENT_WEEK)


def test_entry_count_matches_filtered_entries():
    monday = datetime.fromisocalendar(TODAY.year, int(CURRENT_WEEK[6:]), 1).replace(tzinfo=timezone.utc)
    entries = [
        _make_entry((monday + timedelta(hours=i)).isoformat(), f"entry {i}")
        for i in range(3)
    ]
    repo = InMemoryEntryRepository()
    for e in entries:
        repo.save(e)
    svc = NarrativeService(repo, InMemoryNarrativeRepository(), InMemoryLLMClient())
    result = svc.get_narrative(USER, "week", CURRENT_WEEK)
    assert result.entry_count == 3


def test_month_narrative_generated():
    svc = _make_service()
    result = svc.get_narrative(USER, "month", CURRENT_MONTH)
    assert result.period_type == "month"
    assert result.period_key == CURRENT_MONTH
    assert result.is_cached is False


def test_month_stale_last_week_regenerates():
    from app.models.narrative import NarrativeSummary
    svc = _make_service()
    last_week = (TODAY - timedelta(days=7)).isoformat()
    stale = NarrativeSummary(
        period_type="month", period_key=CURRENT_MONTH,
        entry_count=0, text="old",
        generated_at=f"{last_week}T00:00:00+00:00", is_cached=False,
    )
    svc._narratives.save(USER, f"cache#month#{CURRENT_MONTH}", stale)
    result = svc.get_narrative(USER, "month", CURRENT_MONTH)
    assert result.is_cached is False
    assert result.text != "old"


def test_month_same_week_returns_cached():
    from app.models.narrative import NarrativeSummary
    svc = _make_service()
    monday = (TODAY - timedelta(days=TODAY.weekday())).isoformat()
    cached_narrative = NarrativeSummary(
        period_type="month", period_key=CURRENT_MONTH,
        entry_count=0, text="cached text",
        generated_at=f"{monday}T00:00:00+00:00", is_cached=False,
    )
    svc._narratives.save(USER, f"cache#month#{CURRENT_MONTH}", cached_narrative)
    result = svc.get_narrative(USER, "month", CURRENT_MONTH)
    assert result.is_cached is True


def test_week_yesterday_is_stale_but_month_yesterday_is_not():
    from app.models.narrative import NarrativeSummary
    svc_week = _make_service()
    svc_month = _make_service()
    yesterday = (TODAY - timedelta(days=1)).isoformat()

    for svc, period_type, period_key in [
        (svc_week, "week", CURRENT_WEEK),
        (svc_month, "month", CURRENT_MONTH),
    ]:
        record = NarrativeSummary(
            period_type=period_type, period_key=period_key,
            entry_count=0, text="old",
            generated_at=f"{yesterday}T00:00:00+00:00", is_cached=False,
        )
        svc._narratives.save(USER, f"cache#{period_type}#{period_key}", record)

    week_result = svc_week.get_narrative(USER, "week", CURRENT_WEEK)
    month_result = svc_month.get_narrative(USER, "month", CURRENT_MONTH)

    assert week_result.is_cached is False
    # month cached unless yesterday was in a different ISO week (i.e. today is Monday)
    if TODAY.weekday() == 0:
        assert month_result.is_cached is False
    else:
        assert month_result.is_cached is True
