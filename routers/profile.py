import logging

from fastapi import APIRouter, HTTPException, Request, status

from database.mongo import MongoDB
from models.requests import HealthProfileRequest, HealthProfileResponse

from app import limiter

router = APIRouter(tags=["profile"])
logger = logging.getLogger("agent_health.api")


@router.post("/profile", response_model=HealthProfileResponse, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def save_profile(body: HealthProfileRequest, request: Request):
    """Create or update a user's health profile."""
    user_id = request.headers.get("X-User-Id") or None
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Id header is required to save a health profile.",
        )
    profile_data = body.model_dump()
    await MongoDB.save_profile(user_id=user_id, profile=profile_data)
    logger.info("POST /profile — user='%s', goals='%s'", user_id, body.goals[:80] if body.goals else "")
    return HealthProfileResponse(user_id=user_id, **profile_data)


@router.put("/profile", response_model=HealthProfileResponse, status_code=status.HTTP_200_OK)
@limiter.limit("20/minute")
async def update_profile(body: HealthProfileRequest, request: Request):
    """Alias for POST /profile — accepts PUT from the marketplace proxy."""
    return await save_profile(body, request)


@router.get("/profile", response_model=HealthProfileResponse)
async def get_profile(request: Request):
    """Retrieve a user's stored health profile."""
    user_id = request.headers.get("X-User-Id") or None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-User-Id header is required.")

    profile = await MongoDB.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="No health profile found for this user. Create one via POST /profile.")

    logger.info("GET /profile — user='%s'", user_id)
    return HealthProfileResponse(
        user_id=user_id,
        goals=profile.get("goals", ""),
        fitness_level=profile.get("fitness_level", "beginner"),
        available_equipment=profile.get("available_equipment", []),
        dietary_restrictions=profile.get("dietary_restrictions", []),
        injuries_or_limitations=profile.get("injuries_or_limitations", ""),
        age=profile.get("age"),
        weight_kg=profile.get("weight_kg"),
        height_cm=profile.get("height_cm"),
        sessions_per_week=profile.get("sessions_per_week"),
        minutes_per_session=profile.get("minutes_per_session"),
    )
