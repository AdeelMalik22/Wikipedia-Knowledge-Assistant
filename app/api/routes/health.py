from typing import Any
from fastapi import APIRouter
from app.core.config import settings
from app.core.database import get_connection

router = APIRouter(tags=["health"])

@router.get("/health")
async def health() -> dict[str, Any]:
    try:
        with get_connection() as connection:
            count = connection.execute("SELECT count(*) FROM wiki_chunks").fetchone()[0]
        return {"status": "ok", "database": "connected", "chunks": count, "embedding_model": settings.embedding_model}
    except Exception as exc:
        return {"status": "degraded", "database": "unavailable", "detail": str(exc)}
