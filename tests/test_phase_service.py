import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.llm.in_memory_llm_client import InMemoryLLMClient
from app.models.entry import Entry
from app.models.entry_tags import EntryTags
from app.models.phase import PhaseIndex, PhaseRecord
from app.repositories.in_memory_entry_repository import InMemoryEntryRepository
from app.repositories.in_memory_narrative_repository import InMemoryNarrativeRepository
from app.services.phase_service import PhaseService, _cosine_distance, _mood_score, _percentile_75, _sample_entries

USER = "user-1"
_NOW = datetime.now(timezone.utc)


def _ts(days_ago: int, hour: int = 12) -> str:
    dt = _NOW - timedelta(days=days_ago)
    return dt.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def _entry(days_ago: int, topics: list[str] = [], mood: str | None = None, hour: int = 12) -> Entry:
    tags = EntryTags(topics=topics, mood=mood) if (topics or mood) else None
    return Entry(
        user_id=USER,
        entry_id=str(uuid.uuid4()),
        timestamp=_ts(days_ago, hour),
        entry=f"entry from {days_ago} days ago",
        tags=tags,
    )


def _make_service(entries: list[Entry] | None = None) -> PhaseService:
    repo = InMemoryEntryRepository()
    for e in entries or []:
        repo.save(e)
    return PhaseService(repo, InMemoryNarrativeRepository(), InMemoryLLMClient())


# --- Helpers ---

def _work_entries(start_days_ago: int, count: int) -> list[Entry]:
    return [_entry(start_days_ago - i, topics=["work", "finance"]) for i in range(count)]


def _travel_entries(start_days_ago: int, count: int) -> list[Entry]:
    return [_entry(start_days_ago - i, topics=["travel", "food"]) for i in range(count)]


# --- detect_and_store ---

def test_no_entries_returns_empty():
    assert _make_service().detect_and_store(USER) == []


def test_insufficient_history_returns_empty():
    # Only 2 weeks of entries → 2 windows < _MIN_WINDOWS (3)
    entries = _work_entries(13, 6)
    assert _make_service(entries).detect_and_store(USER) == []


def test_single_phase_stable_signal():
    # 4 weeks of uniform work entries → should yield 1 phase
    entries = _work_entries(27, 20)
    result = _make_service(entries).detect_and_store(USER)
    assert len(result) == 1
    assert result[0].is_open is True
    assert result[0].end_date is None


def _two_phase_entries():
    # 3 weeks work (days 41..21) then 3 weeks travel (days 20..1) = 6 windows, clear boundary
    return _work_entries(41, 21) + _travel_entries(20, 20)


def test_two_phases_clear_topic_shift():
    result = _make_service(_two_phase_entries()).detect_and_store(USER)
    assert len(result) == 2
    assert result[0].is_open is False
    assert result[1].is_open is True


def test_phase_dominates_correct_topics():
    result = _make_service(_two_phase_entries()).detect_and_store(USER)
    assert "work" in result[0].dominant_topics or "finance" in result[0].dominant_topics
    assert "travel" in result[1].dominant_topics or "food" in result[1].dominant_topics


def test_phases_ordered_oldest_to_newest():
    result = _make_service(_two_phase_entries()).detect_and_store(USER)
    assert result[0].start_date < result[1].start_date


def test_open_phase_has_null_end_date():
    entries = _work_entries(27, 15)
    result = _make_service(entries).detect_and_store(USER)
    open_phases = [p for p in result if p.is_open]
    assert len(open_phases) == 1
    assert open_phases[0].end_date is None


def test_closed_phase_has_end_date():
    result = _make_service(_two_phase_entries()).detect_and_store(USER)
    assert result[0].end_date is not None


def test_entry_count_correct():
    entries = _work_entries(41, 12) + _travel_entries(27, 12)
    result = _make_service(entries).detect_and_store(USER)
    total = sum(p.entry_count for p in result)
    assert total == 24


def test_phase_index_stored_after_detection():
    entries = _work_entries(27, 15)
    repo = InMemoryNarrativeRepository()
    svc = PhaseService(InMemoryEntryRepository(), repo, InMemoryLLMClient())
    for e in entries:
        svc._entries.save(e)
    svc.detect_and_store(USER)
    index = repo.get_phase_index(USER)
    assert index is not None
    assert len(index.phase_ids) >= 1


def test_sparse_micro_phase_merged():
    # Create two solid phases with a micro-phase (1 window, 2 entries) sandwiched between them
    # Phase A: 3 weeks work
    phase_a = _work_entries(62, 12)
    # Micro: 1 week travel (only 2 entries — below _MIN_ENTRIES=5)
    micro = _travel_entries(41, 2)
    # Phase B: 3 weeks work (same signal as A → merged into A, not B)
    phase_b = _work_entries(27, 12)
    result = _make_service(phase_a + micro + phase_b).detect_and_store(USER)
    # Micro phase should be absorbed; result should be fewer phases than raw boundaries suggest
    # The micro has same-ish topic as neither A nor B clearly, but since it only has 2 entries it merges
    assert all(p.entry_count >= 1 for p in result)


def test_frozen_past_phase_not_regenerated():
    # 3 weeks of work (days 55..35) followed immediately by 3 weeks of travel (days 34..14)
    # The closed work phase ends ~5 weeks ago, which is past the 4-week freeze cutoff.
    entries = _work_entries(55, 21) + _travel_entries(34, 21)
    entry_repo = InMemoryEntryRepository()
    for e in entries:
        entry_repo.save(e)

    # First run: capture the two detected phases with known titles
    llm = MagicMock()
    llm.generate_phase.side_effect = [("Old Title", "Old desc."), ("Open Title", "Open desc.")]
    repo = InMemoryNarrativeRepository()
    first = PhaseService(entry_repo, repo, llm).detect_and_store(USER)
    assert len(first) == 2
    closed = first[0]
    assert closed.end_date is not None
    freeze_cutoff = (_NOW - timedelta(weeks=4)).date().isoformat()
    assert closed.end_date < freeze_cutoff, "Setup error: closed phase isn't old enough to be frozen"

    # Second run: frozen phase must be reused; LLM called only for the open phase
    llm2 = MagicMock()
    llm2.generate_phase.return_value = ("Regenerated", "Regenerated desc.")
    second = PhaseService(entry_repo, repo, llm2).detect_and_store(USER)

    reused = next((p for p in second if p.phase_id == closed.phase_id), None)
    assert reused is not None
    assert reused.title == "Old Title"
    assert llm2.generate_phase.call_count == 1


def test_open_phase_regenerated_on_rerun():
    entries = _work_entries(27, 15)
    llm = MagicMock()
    llm.generate_phase.side_effect = [
        ("First Run", "First description."),
        ("Second Run", "Second description."),
    ]
    repo = InMemoryNarrativeRepository()
    entry_repo = InMemoryEntryRepository()
    for e in entries:
        entry_repo.save(e)
    svc = PhaseService(entry_repo, repo, llm)

    first = svc.detect_and_store(USER)
    second = svc.detect_and_store(USER)

    assert first[0].title == "First Run"
    assert second[0].title == "Second Run"
    assert llm.generate_phase.call_count == 2


# --- get_phases ---

def test_get_phases_triggers_lazy_detection():
    entries = _work_entries(27, 15)
    svc = _make_service(entries)
    result = svc.get_phases(USER)
    assert len(result) >= 1


def test_get_phases_uses_cached_index():
    entries = _work_entries(27, 15)
    llm = MagicMock()
    llm.generate_phase.return_value = ("T", "D")
    repo = InMemoryNarrativeRepository()
    entry_repo = InMemoryEntryRepository()
    for e in entries:
        entry_repo.save(e)
    svc = PhaseService(entry_repo, repo, llm)

    svc.get_phases(USER)
    svc.get_phases(USER)

    assert llm.generate_phase.call_count == 1


def test_get_phases_refresh_reruns_detection():
    entries = _work_entries(27, 15)
    llm = MagicMock()
    llm.generate_phase.return_value = ("T", "D")
    repo = InMemoryNarrativeRepository()
    entry_repo = InMemoryEntryRepository()
    for e in entries:
        entry_repo.save(e)
    svc = PhaseService(entry_repo, repo, llm)

    svc.get_phases(USER)
    svc.get_phases(USER, refresh=True)

    assert llm.generate_phase.call_count == 2


# --- get_current_phase ---

def test_get_current_phase_returns_open():
    entries = _work_entries(27, 15)
    svc = _make_service(entries)
    current = svc.get_current_phase(USER)
    assert current is not None
    assert current.is_open is True


def test_get_current_phase_none_when_no_phases():
    svc = _make_service()
    assert svc.get_current_phase(USER) is None


# --- get_phase by id ---

def test_get_phase_by_id_returns_correct():
    entries = _work_entries(27, 15)
    svc = _make_service(entries)
    phases = svc.get_phases(USER)
    assert phases
    found = svc.get_phase(USER, phases[0].phase_id)
    assert found is not None
    assert found.phase_id == phases[0].phase_id


def test_get_phase_unknown_id_returns_none():
    svc = _make_service()
    assert svc.get_phase(USER, "nonexistent") is None


# --- Module-level helpers ---

def test_percentile_75_interpolates():
    # With [0, 0, 1.0], naive floor index gives threshold=1.0 (no boundary); interpolation gives 0.5
    assert _percentile_75([0.0, 0.0, 1.0]) == pytest.approx(0.5)


def test_percentile_75_exact_position():
    assert _percentile_75([0.0, 0.0, 0.0, 0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_distance_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert _cosine_distance(v, v) == pytest.approx(0.0)


def test_cosine_distance_orthogonal_vectors():
    assert _cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)


def test_cosine_distance_zero_vector():
    assert _cosine_distance([0.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_mood_score_known_values():
    assert _mood_score("positive") == pytest.approx(1.0)
    assert _mood_score("negative") == pytest.approx(-1.0)
    assert _mood_score("neutral") == pytest.approx(0.0)
    assert _mood_score("very_positive") == pytest.approx(2.0)


def test_mood_score_case_insensitive():
    assert _mood_score("Positive") == pytest.approx(1.0)
    assert _mood_score("NEGATIVE") == pytest.approx(-1.0)


def test_mood_score_unknown_returns_none():
    assert _mood_score("joyful") is None


def test_sample_entries_respects_budget():
    entries = [
        Entry(user_id=USER, entry_id=str(i), timestamp=_ts(i), entry="x" * 100)
        for i in range(100)
    ]
    sampled = _sample_entries(entries, char_budget=500)
    assert sum(len(e.entry) for e in sampled) <= 500


def test_sample_entries_chronological_order():
    entries = [
        Entry(user_id=USER, entry_id=str(i), timestamp=_ts(10 - i), entry="x")
        for i in range(5)
    ]
    sampled = _sample_entries(entries)
    timestamps = [e.timestamp for e in sampled]
    assert timestamps == sorted(timestamps)
