from datetime import datetime, timedelta, timezone

from app.llm.llm_client import LLMClient
from app.models.narrative import NarrativeSummary
from app.repositories.entry_repository import EntryRepository
from app.repositories.narrative_repository import NarrativeRepository


class NarrativeService:
    def __init__(
        self,
        entry_repo: EntryRepository,
        narrative_repo: NarrativeRepository,
        llm_client: LLMClient,
    ) -> None:
        self._entries = entry_repo
        self._narratives = narrative_repo
        self._llm = llm_client

    def get_narrative(
        self,
        user_id: str,
        period_type: str,
        period_key: str,
        force_refresh: bool = False,
    ) -> NarrativeSummary:
        record_id = f"cache#{period_type}#{period_key}"
        is_current = self._is_current_period(period_type, period_key)

        if not force_refresh:
            cached = self._narratives.get(user_id, record_id)
            if cached:
                stale = is_current and self._is_stale(period_type, cached.generated_at)
                if not stale:
                    return cached.model_copy(update={"is_cached": True})

        entries = self._entries_for_period(user_id, period_type, period_key)
        text = self._llm.generate_narrative(entries, period_key)

        summary = NarrativeSummary(
            period_type=period_type,
            period_key=period_key,
            entry_count=len(entries),
            text=text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            is_cached=False,
        )
        self._narratives.save(user_id, record_id, summary)
        return summary

    def _is_stale(self, period_type: str, generated_at: str) -> bool:
        now = datetime.now(timezone.utc)
        generated = datetime.strptime(generated_at[:10], "%Y-%m-%d")
        if period_type == "week":
            return generated_at[:10] != now.date().isoformat()
        return generated.strftime("%G-W%V") != now.strftime("%G-W%V")

    def _is_current_period(self, period_type: str, period_key: str) -> bool:
        today = datetime.now(timezone.utc).date()
        if period_type == "week":
            return period_key == today.strftime("%G-W%V")
        return period_key == today.strftime("%Y-%m")

    def _entries_for_period(self, user_id: str, period_type: str, period_key: str) -> list:
        all_entries = self._entries.list_by_user(user_id)
        if period_type == "week":
            year, week = int(period_key[:4]), int(period_key[6:])
            monday = datetime.fromisocalendar(year, week, 1).replace(tzinfo=timezone.utc)
            next_monday = monday + timedelta(days=7)
            return [e for e in all_entries
                    if monday.isoformat() <= e.timestamp < next_monday.isoformat()]
        return [e for e in all_entries if e.timestamp[:7] == period_key]
