from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_current_user_id, get_phase_service
from app.models.phase import PhaseRecord
from app.services.phase_service import PhaseService

router = APIRouter(prefix="/phases", tags=["phases"])


@router.get("", response_model=list[PhaseRecord])
def get_phases(
    refresh: bool = False,
    user_id: str = Depends(get_current_user_id),
    service: PhaseService = Depends(get_phase_service),
) -> list[PhaseRecord]:
    return service.get_phases(user_id, refresh=refresh)


# /current must be declared before /{phase_id} to avoid being captured as a phase_id
@router.get("/current", response_model=PhaseRecord | None)
def get_current_phase(
    user_id: str = Depends(get_current_user_id),
    service: PhaseService = Depends(get_phase_service),
) -> PhaseRecord | None:
    return service.get_current_phase(user_id)


@router.get("/{phase_id}", response_model=PhaseRecord)
def get_phase(
    phase_id: str,
    user_id: str = Depends(get_current_user_id),
    service: PhaseService = Depends(get_phase_service),
) -> PhaseRecord:
    phase = service.get_phase(user_id, phase_id)
    if phase is None:
        raise HTTPException(status_code=404, detail="Phase not found")
    return phase
