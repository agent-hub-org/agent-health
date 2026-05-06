from fastapi import APIRouter
from fastapi.responses import Response

from agent_common.metrics import metrics_response

router = APIRouter(tags=["admin"])


@router.get("/metrics")
async def metrics():
    content, content_type = metrics_response()
    return Response(content=content, media_type=content_type)


@router.get("/health")
async def health():
    return {"status": "ok", "service": "agent-health"}
