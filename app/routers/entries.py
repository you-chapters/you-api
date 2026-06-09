from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user_id, get_narrative_service, get_service
from app.models.entry import CreateEntryRequest, Entry, SearchRequest, SearchResult
from app.models.narrative import NarrativeSummary
from app.models.summary import PeriodSummary
from app.services.entry_service import EntryService
from app.services.narrative_service import NarrativeService

router = APIRouter(prefix="/entries", tags=["entries"])


@router.post("", response_model=Entry, status_code=201)
def create_entry(request: CreateEntryRequest, user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_service)) -> Entry:
    return service.create_entry(user_id, request)


@router.post("/search", response_model=SearchResult)
def search_entries(request: SearchRequest, user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_service)) -> SearchResult:
    return SearchResult(entries=service.search_entries(user_id, request.query))


@router.get("/summary", response_model=PeriodSummary)
def get_summary(
    period: int = 30,
    user_id: str = Depends(get_current_user_id),
    service: EntryService = Depends(get_service),
) -> PeriodSummary:
    return service.get_summary(user_id, period_days=period)


@router.get("/narrative", response_model=NarrativeSummary)
def get_narrative(
    type: str = "week",
    key: str | None = None,
    refresh: bool = False,
    user_id: str = Depends(get_current_user_id),
    service: NarrativeService = Depends(get_narrative_service),
) -> NarrativeSummary:
    if type not in ("week", "month"):
        raise HTTPException(status_code=422, detail="type must be 'week' or 'month'")
    today = datetime.now(timezone.utc).date()
    resolved_key = key or (today.strftime("%G-W%V") if type == "week" else today.strftime("%Y-%m"))
    return service.get_narrative(user_id, period_type=type, period_key=resolved_key, force_refresh=refresh)


@router.get("/{entry_id}", response_model=Entry)
def get_entry(entry_id: str, user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_service)) -> Entry:
    entry = service.get_entry(user_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.get("", response_model=list[Entry])
def list_entries(
    from_date: date | None = None,
    to_date: date | None = None,
    user_id: str = Depends(get_current_user_id),
    service: EntryService = Depends(get_service),
) -> list[Entry]:
    return service.list_entries(user_id, from_date=from_date, to_date=to_date)
