"""健康检查 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import HealthResponse
from app.services.llm.factory import get_llm_provider

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    provider = get_llm_provider()
    llm_available = await provider.health_check()

    overall = "ok" if db_ok else "degraded"
    return HealthResponse(
        status=overall,
        database="connected" if db_ok else "disconnected",
        llm_provider=provider.provider_name,
        llm_available=llm_available,
    )
