import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from database.mongo import MongoDB
from models.requests import ProgressLogRequest, NutritionLogRequest

from app import limiter

router = APIRouter(tags=["progress"])
logger = logging.getLogger("agent_health.api")


@router.post("/progress")
@limiter.limit("60/minute")
async def log_progress(body: ProgressLogRequest, request: Request):
    """Log a fitness or health measurement."""
    user_id = request.headers.get("X-User-Id") or None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    date = body.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await MongoDB.log_progress(
        user_id=user_id,
        metric_type=body.metric_type,
        value=body.value,
        unit=body.unit,
        notes=body.notes,
        date=date,
    )
    return {"success": True, "date": date}


@router.get("/progress")
@limiter.limit("60/minute")
async def get_progress(request: Request, metric_type: str | None = None, days: int = 30):
    """Get recent progress logs for the user."""
    user_id = request.headers.get("X-User-Id") or None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    if metric_type:
        data = await MongoDB.get_progress(user_id=user_id, metric_type=metric_type, days=days)
    else:
        data = await MongoDB.get_all_progress(user_id=user_id, days=days)
    return {"progress": data, "days": days}


@router.post("/nutrition")
@limiter.limit("60/minute")
async def log_nutrition(body: NutritionLogRequest, request: Request):
    """Log a meal or nutrition entry."""
    user_id = request.headers.get("X-User-Id") or None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    date = body.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await MongoDB.log_nutrition(
        user_id=user_id,
        meal_description=body.meal_description,
        calories_kcal=body.calories_kcal,
        protein_g=body.protein_g,
        carbs_g=body.carbs_g,
        fat_g=body.fat_g,
        meal_type=body.meal_type,
        date=date,
    )
    daily = await MongoDB.get_daily_nutrition_total(user_id=user_id, date=date)
    return {"success": True, "date": date, "daily_total": daily}


@router.get("/nutrition")
@limiter.limit("60/minute")
async def get_nutrition(request: Request, days: int = 7):
    """Get recent nutrition logs for the user."""
    user_id = request.headers.get("X-User-Id") or None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    logs = await MongoDB.get_nutrition_logs(user_id=user_id, days=days)
    return {"logs": logs, "days": days}


@router.get("/export/plan/{session_id}")
async def export_plan(session_id: str):
    """Download the most recently generated fitness plan for a session."""
    file_meta = await MongoDB.get_latest_plan(session_id)
    if not file_meta:
        raise HTTPException(status_code=404, detail="No fitness plan found for this session. Ask the agent to generate one first.")

    result = await MongoDB.retrieve_file(file_meta["file_id"])
    if not result:
        raise HTTPException(status_code=404, detail="Plan file not found in storage.")

    data, meta = result
    filename = meta.get("filename", "fitness-plan.pdf")
    media_type = "application/pdf" if filename.endswith(".pdf") else "text/markdown"

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/download/{file_id}")
async def download_file(file_id: str):
    """Download any generated file by its file_id."""
    result = await MongoDB.retrieve_file(file_id)
    if not result:
        raise HTTPException(status_code=404, detail="File not found.")

    data, meta = result
    filename = meta.get("filename", "download")

    if filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif filename.endswith(".md"):
        media_type = "text/markdown"
    else:
        media_type = "application/octet-stream"

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
