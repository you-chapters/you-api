from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user_id, get_narrative_service, get_qa_service, get_entry_service, get_usage_limiter
from app.models.entry import CreateEntryRequest, Entry, SearchRequest, SearchResult
from app.models.narrative import NarrativeSummary
from app.models.qa import QaRequest, QaResult
from app.models.summary import PeriodSummary
from app.services.entry_service import EntryService
from app.services.narrative_service import NarrativeService
from app.services.qa_service import QaService
from app.usage_limiter import UsageLimiter

router = APIRouter(prefix="/entries", tags=["entries"])


@router.post("", response_model=Entry, status_code=201)
def create_entry(request: CreateEntryRequest, user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_entry_service), limiter: UsageLimiter = Depends(get_usage_limiter)) -> Entry:
    _require_capacity(limiter, user_id, "create_entry")
    return service.create_entry(user_id, request)


@router.post("/search", response_model=SearchResult)
def search_entries(request: SearchRequest, user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_entry_service), limiter: UsageLimiter = Depends(get_usage_limiter)) -> SearchResult:
    _require_capacity(limiter, user_id, "search")
    return SearchResult(entries=service.search_entries(user_id, request.query))


@router.post("/ask", response_model=QaResult)
def ask_question(request: QaRequest, user_id: str = Depends(get_current_user_id), qa_service: QaService = Depends(get_qa_service), limiter: UsageLimiter = Depends(get_usage_limiter)) -> QaResult:
    _require_capacity(limiter, user_id, "ask")
    return qa_service.ask_question(user_id, request.question)


@router.get("/summary", response_model=PeriodSummary)
def get_summary(
    period: int = 30,
    user_id: str = Depends(get_current_user_id),
    service: EntryService = Depends(get_entry_service),
) -> PeriodSummary:
    return service.get_summary(user_id, period_days=period)


@router.get("/narrative", response_model=NarrativeSummary)
def get_narrative(
    type: str = "week",
    key: str | None = None,
    refresh: bool = False,
    user_id: str = Depends(get_current_user_id),
    service: NarrativeService = Depends(get_narrative_service),
    limiter: UsageLimiter = Depends(get_usage_limiter),
) -> NarrativeSummary:
    if type not in ("week", "month"):
        raise HTTPException(status_code=422, detail="type must be 'week' or 'month'")
    if refresh:
        _require_capacity(limiter, user_id, "narrative_refresh")
    today = datetime.now(timezone.utc).date()
    resolved_key = key or (today.strftime("%G-W%V") if type == "week" else today.strftime("%Y-%m"))
    return service.get_narrative(user_id, period_type=type, period_key=resolved_key, force_refresh=refresh)


def _require_capacity(limiter: UsageLimiter, user_id: str, operation: str) -> None:
    if not limiter.allow(user_id, operation):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")


@router.get("/on-this-day", response_model=list[Entry])
def get_on_this_day(
    user_id: str = Depends(get_current_user_id),
    service: EntryService = Depends(get_entry_service),
) -> list[Entry]:
    return service.get_on_this_day(user_id)


@router.get("/{entry_id}", response_model=Entry)
def get_entry(entry_id: str, user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_entry_service)) -> Entry:
    entry = service.get_entry(user_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.get("", response_model=list[Entry])
def list_entries(
    from_date: date | None = None,
    to_date: date | None = None,
    user_id: str = Depends(get_current_user_id),
    service: EntryService = Depends(get_entry_service),
) -> list[Entry]:
    return service.list_entries(user_id, from_date=from_date, to_date=to_date)
