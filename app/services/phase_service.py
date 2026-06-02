import math
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.llm.llm_client import LLMClient
from app.models.entry import Entry
from app.models.phase import PhaseIndex, PhaseRecord
from app.repositories.entry_repository import EntryRepository
from app.repositories.narrative_repository import NarrativeRepository

_TOPICS = [
    "work", "family", "travel", "health", "reading",
    "finance", "relationships", "hobbies", "food", "exercise",
]
_MOOD_MAP: dict[str, float] = {
    "very positive": 2.0,
    "positive": 1.0,
    "neutral": 0.0,
    "negative": -1.0,
    "very negative": -2.0,
}
_WINDOW_DAYS = 7
_MIN_WINDOWS = 3
_MIN_ENTRIES = 5
_FREEZE_WEEKS = 4
_SAMPLE_CHARS = 40_000


@dataclass
class _Window:
    start: datetime
    entries: list[Entry]
    topic_vector: list[float] = field(default_factory=list)
    mood_score: float = 0.0
    people_diversity: int = 0
    location_novelty: float = 0.0


class PhaseService:
    def __init__(
        self,
        entry_repo: EntryRepository,
        narrative_repo: NarrativeRepository,
        llm_client: LLMClient,
    ) -> None:
        self._entries = entry_repo
        self._narratives = narrative_repo
        self._llm = llm_client

    def detect_and_store(self, user_id: str) -> list[PhaseRecord]:
        # TODO: fetches full entry history — add a lookback limit (e.g. 12 months) when user base grows
        all_entries = sorted(
            self._entries.list_by_user(user_id), key=lambda e: e.timestamp
        )
        topics = sorted(
            set(_TOPICS) | {t for e in all_entries if e.tags for t in (e.tags.topics or [])}
        )
        windows = self._build_windows(all_entries)
        if len(windows) < _MIN_WINDOWS:
            return []
        self._compute_signals(windows, topics)
        boundaries = self._detect_boundaries(windows)
        phase_groups = self._group_into_phases(windows, boundaries)
        phase_groups = self._merge_sparse(phase_groups, topics)
        if not phase_groups:
            return []
        return self._name_and_store(user_id, phase_groups)

    def get_phases(self, user_id: str, refresh: bool = False) -> list[PhaseRecord]:
        index = self._narratives.get_phase_index(user_id)
        if index is None or refresh:
            return self.detect_and_store(user_id)
        return self._narratives.batch_get_phases(user_id, index.phase_ids)

    def get_phase(self, user_id: str, phase_id: str) -> PhaseRecord | None:
        return self._narratives.get_phase(user_id, phase_id)

    def get_current_phase(self, user_id: str) -> PhaseRecord | None:
        for phase in self.get_phases(user_id):
            if phase.is_open:
                return phase
        return None

    # --- Window building ---

    def _build_windows(self, entries: list[Entry]) -> list[_Window]:
        if not entries:
            return []
        start = datetime.fromisoformat(entries[0].timestamp)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        end = datetime.fromisoformat(entries[-1].timestamp)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        windows: list[_Window] = []
        cursor = start
        while cursor <= end:
            next_cursor = cursor + timedelta(days=_WINDOW_DAYS)
            window_entries = [
                e for e in entries
                if cursor.isoformat() <= e.timestamp < next_cursor.isoformat()
            ]
            windows.append(_Window(start=cursor, entries=window_entries))
            cursor = next_cursor
        return windows

    # --- Signal computation ---

    def _compute_signals(self, windows: list[_Window], topics: list[str]) -> None:
        for i, w in enumerate(windows):
            w.topic_vector = self._topic_vector(w.entries, topics)
            w.mood_score = self._mean_mood(w.entries)
            w.people_diversity = self._people_diversity(w.entries)
            w.location_novelty = self._location_novelty(windows, i)

    def _topic_vector(self, entries: list[Entry], topics: list[str]) -> list[float]:
        if not entries:
            return [0.0] * len(topics)
        return [
            sum(1 for e in entries if e.tags and topic in (e.tags.topics or [])) / len(entries)
            for topic in topics
        ]

    def _mean_mood(self, entries: list[Entry]) -> float:
        scores = [
            _mood_score(e.tags.mood)
            for e in entries
            if e.tags and e.tags.mood and _mood_score(e.tags.mood) is not None
        ]
        return sum(scores) / len(scores) if scores else 0.0  # type: ignore[arg-type]

    def _people_diversity(self, entries: list[Entry]) -> int:
        people: set[str] = set()
        for e in entries:
            if e.tags and e.tags.people:
                people.update(e.tags.people)
        return len(people)

    def _location_novelty(self, windows: list[_Window], idx: int) -> float:
        current: set[str] = set()
        for e in windows[idx].entries:
            if e.tags and e.tags.locations:
                current.update(e.tags.locations)
        if not current:
            return 0.0
        prior: set[str] = set()
        for j in range(max(0, idx - 4), idx):
            for e in windows[j].entries:
                if e.tags and e.tags.locations:
                    prior.update(e.tags.locations)
        return len(current - prior) / len(current)

    # --- Boundary detection ---

    def _detect_boundaries(self, windows: list[_Window]) -> list[int]:
        if len(windows) < 2:
            return [0]
        distances = [
            _cosine_distance(windows[i].topic_vector, windows[i + 1].topic_vector)
            for i in range(len(windows) - 1)
        ]
        sorted_d = sorted(distances)
        threshold = _percentile_75(sorted_d)

        boundaries: set[int] = {0}
        for i, dist in enumerate(distances):
            if dist > threshold:
                boundaries.add(i + 1)
            elif dist > 0.5 * threshold and self._has_sustained_mood_shift(windows, i + 1, min_windows=3):
                # Near-threshold topic shift reinforced by mood
                boundaries.add(i + 1)
            elif self._has_location_burst(windows, i + 1):
                boundaries.add(i + 1)
            elif self._has_sustained_mood_shift(windows, i + 1, min_windows=6):
                # Mood alone as boundary requires stronger persistence
                boundaries.add(i + 1)
        return sorted(boundaries)

    def _has_sustained_mood_shift(self, windows: list[_Window], after_idx: int, min_windows: int) -> bool:
        if after_idx == 0 or after_idx + min_windows > len(windows):
            return False
        before = windows[max(0, after_idx - min_windows):after_idx]
        after = windows[after_idx:after_idx + min_windows]
        if not before or not after:
            return False
        before_mean = sum(w.mood_score for w in before) / len(before)
        after_mean = sum(w.mood_score for w in after) / len(after)
        # Sign flip in mean mood across the boundary
        return before_mean * after_mean < 0

    def _has_location_burst(self, windows: list[_Window], idx: int) -> bool:
        if idx >= len(windows) or windows[idx].location_novelty <= 0.5:
            return False
        prior_count = min(idx, 4)
        if prior_count == 0:
            return False
        prior_avg = sum(windows[j].location_novelty for j in range(idx - prior_count, idx)) / prior_count
        return prior_avg < 0.1

    # --- Phase grouping and sparse merging ---

    def _group_into_phases(self, windows: list[_Window], boundaries: list[int]) -> list[list[_Window]]:
        phases: list[list[_Window]] = []
        for i, start_idx in enumerate(boundaries):
            end_idx = boundaries[i + 1] if i + 1 < len(boundaries) else len(windows)
            phases.append(windows[start_idx:end_idx])
        return phases

    def _merge_sparse(self, phases: list[list[_Window]], topics: list[str]) -> list[list[_Window]]:
        changed = True
        while changed and len(phases) > 1:
            changed = False
            for i in range(len(phases)):
                phase = phases[i]
                if len(phase) >= _MIN_WINDOWS and sum(len(w.entries) for w in phase) >= _MIN_ENTRIES:
                    continue
                phase_vec = _avg_topic_vector(phase, topics)
                if i == 0:
                    phases = [phase + phases[1]] + phases[2:]
                elif i == len(phases) - 1:
                    phases = phases[:-2] + [phases[-2] + phase]
                else:
                    left_vec = _avg_topic_vector(phases[i - 1], topics)
                    right_vec = _avg_topic_vector(phases[i + 1], topics)
                    if _cosine_distance(phase_vec, left_vec) <= _cosine_distance(phase_vec, right_vec):
                        phases = phases[: i - 1] + [phases[i - 1] + phase] + phases[i + 1 :]
                    else:
                        phases = phases[:i] + [phase + phases[i + 1]] + phases[i + 2 :]
                changed = True
                break
        return phases

    # --- LLM naming and storage ---

    def _name_and_store(self, user_id: str, phase_groups: list[list[_Window]]) -> list[PhaseRecord]:
        now = datetime.now(timezone.utc)
        freeze_cutoff = (now - timedelta(weeks=_FREEZE_WEEKS)).date().isoformat()

        existing_index = self._narratives.get_phase_index(user_id)
        existing_ids = existing_index.phase_ids if existing_index else []
        existing_records = self._narratives.batch_get_phases(user_id, existing_ids) if existing_ids else []
        frozen = {r.start_date: r for r in existing_records if r.end_date and r.end_date < freeze_cutoff}

        records: list[PhaseRecord] = []
        last_idx = len(phase_groups) - 1

        for idx, phase_windows in enumerate(phase_groups):
            start_date = phase_windows[0].start.date().isoformat()
            is_open = idx == last_idx
            end_date = (
                None if is_open
                else (phase_windows[-1].start + timedelta(days=_WINDOW_DAYS - 1)).date().isoformat()
            )

            if start_date in frozen:
                records.append(frozen[start_date])
                continue

            phase_entries = [e for w in phase_windows for e in w.entries]
            signals = self._aggregate_signals(phase_entries)
            hint = self._build_hint(signals)
            signals_summary = self._build_signals_summary(signals, start_date, end_date)
            sampled = _sample_entries(phase_entries)
            title, description = self._llm.generate_phase(sampled, signals_summary, hint)

            existing_for_start = next(
                (r for r in existing_records if r.start_date == start_date), None
            )
            phase_id = existing_for_start.phase_id if existing_for_start else str(uuid.uuid4())

            record = PhaseRecord(
                phase_id=phase_id,
                title=title,
                description=description,
                start_date=start_date,
                end_date=end_date,
                entry_count=len(phase_entries),
                dominant_topics=signals["dominant_topics"],
                mean_mood=signals["mean_mood"],
                top_people=signals["top_people"],
                top_locations=signals["top_locations"],
                generated_at=now.isoformat(),
                is_open=is_open,
            )
            self._narratives.save_phase(user_id, phase_id, record)
            records.append(record)

        index = PhaseIndex(
            phase_ids=[r.phase_id for r in records],
            last_detected_at=now.isoformat(),
            window_size_days=_WINDOW_DAYS,
        )
        self._narratives.save_phase_index(user_id, index)
        return records

    def _aggregate_signals(self, entries: list[Entry]) -> dict:
        topic_counts: Counter = Counter()
        people_counts: Counter = Counter()
        location_counts: Counter = Counter()
        mood_scores: list[float] = []
        for e in entries:
            if not e.tags:
                continue
            for t in e.tags.topics or []:
                topic_counts[t] += 1
            for p in e.tags.people or []:
                people_counts[p] += 1
            for loc in e.tags.locations or []:
                location_counts[loc] += 1
            if e.tags.mood:
                score = _mood_score(e.tags.mood)
                if score is not None:
                    mood_scores.append(score)
        return {
            "dominant_topics": [t for t, _ in topic_counts.most_common(3)],
            "mean_mood": sum(mood_scores) / len(mood_scores) if mood_scores else 0.0,
            "top_people": [p for p, _ in people_counts.most_common(3)],
            "top_locations": [loc for loc, _ in location_counts.most_common(3)],
        }

    def _build_hint(self, signals: dict) -> str:
        parts: list[str] = []
        if signals["dominant_topics"]:
            parts.append("Heavy " + " + ".join(signals["dominant_topics"][:2]))
        mood = signals["mean_mood"]
        if mood > 0.5:
            parts.append("positive mood")
        elif mood < -0.5:
            parts.append("declining mood")
        if signals["top_people"]:
            parts.append("people: " + ", ".join(signals["top_people"][:2]))
        return " + ".join(parts) if parts else "mixed signals"

    def _build_signals_summary(self, signals: dict, start_date: str, end_date: str | None) -> str:
        period = f"{start_date} to {end_date or 'present'}"
        topics = ", ".join(signals["dominant_topics"]) or "none"
        mood = f"{signals['mean_mood']:.1f}"
        people = ", ".join(signals["top_people"]) or "none"
        locations = ", ".join(signals["top_locations"]) or "none"
        return f"Period: {period}. Topics: {topics}. Mean mood: {mood}. People: {people}. Locations: {locations}."


# --- Module-level helpers ---

def _percentile_75(sorted_values: list[float]) -> float:
    """75th percentile via linear interpolation (avoids threshold == max edge case)."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_values[0]
    idx = 0.75 * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def _cosine_distance(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a ** 2 for a in v1))
    mag2 = math.sqrt(sum(b ** 2 for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 1.0
    return 1.0 - dot / (mag1 * mag2)


def _avg_topic_vector(phase_windows: list[_Window], topics: list[str]) -> list[float]:
    if not phase_windows:
        return [0.0] * len(topics)
    n = len(phase_windows)
    return [sum(w.topic_vector[i] for w in phase_windows) / n for i in range(len(topics))]


def _mood_score(mood: str) -> float | None:
    key = mood.lower().strip().replace("_", " ")
    score = _MOOD_MAP.get(key)
    if score is not None:
        return score
    for k, v in _MOOD_MAP.items():
        if k in key:
            return v
    return None


def _sample_entries(entries: list[Entry], char_budget: int = _SAMPLE_CHARS) -> list[Entry]:
    result: list[Entry] = []
    total = 0
    for e in sorted(entries, key=lambda e: e.timestamp):
        if total + len(e.entry) > char_budget:
            break
        result.append(e)
        total += len(e.entry)
    return result
