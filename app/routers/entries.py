from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user_id, get_service
from app.models.entry import CreateEntryRequest, Entry, SearchRequest, SearchResult
from app.services.entry_service import EntryService

router = APIRouter(prefix="/entries", tags=["entries"])


@router.post("", response_model=Entry, status_code=201)
def create_entry(request: CreateEntryRequest, user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_service)) -> Entry:
    return service.create_entry(user_id, request)


@router.post("/search", response_model=SearchResult)
def search_entries(request: SearchRequest, user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_service)) -> SearchResult:
    return SearchResult(entries=service.search_entries(user_id, request.query))


@router.get("/{entry_id}", response_model=Entry)
def get_entry(entry_id: str, user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_service)) -> Entry:
    entry = service.get_entry(user_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.get("", response_model=list[Entry])
def list_entries(user_id: str = Depends(get_current_user_id), service: EntryService = Depends(get_service)) -> list[Entry]:
    return service.list_entries(user_id)