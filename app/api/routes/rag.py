import json
from urllib.parse import quote
from urllib.request import Request, urlopen
from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.schemas.rag import AskRequest, IngestRequest
from app.services.rag import ingest, retrieve

router = APIRouter(tags=["rag"])

@router.post("/ingest")
async def ingest_document(request: IngestRequest):
    return ingest(request.title, request.text, request.source_url)

@router.post("/ingest/wikipedia/{title}")
async def ingest_wikipedia(title: str):
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_"))
        request = Request(url, headers={"User-Agent": settings.wikipedia_user_agent})
        with urlopen(request, timeout=15) as response:
            page = json.load(response)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Wikipedia request failed: {exc}") from exc
    return ingest(page["title"], page.get("extract", ""), page.get("content_urls", {}).get("desktop", {}).get("page"))

@router.post("/ask")
async def ask(request: AskRequest):
    result = retrieve(request.question, request.top_k)
    return {"question": request.question, "answer": "Generation is intentionally left visible: use the context below with your LLM.", "context": result["context"], "sources": result["sources"], "debug": {"retrieved": len(result["sources"]), "elapsed_ms": result["elapsed_ms"]}}
