"""Small, inspectable Wikipedia RAG API."""
import os, time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen
import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rag:rag@localhost:5432/wikipedia_rag")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
TOP_K = int(os.getenv("TOP_K", "5")); _model: SentenceTransformer | None = None

class IngestRequest(BaseModel):
    title: str = Field(min_length=1); text: str = Field(min_length=20); source_url: str | None = None
class AskRequest(BaseModel):
    question: str = Field(min_length=3); top_k: int = Field(default=TOP_K, ge=1, le=20)

def embedding_model() -> SentenceTransformer:
    global _model
    if _model is None: _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model
def chunks(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    words = text.split(); step = size - overlap
    return [part for start in range(0, len(words), step) if (part := " ".join(words[start:start + size]).strip())]
def db() -> psycopg.Connection: return psycopg.connect(DATABASE_URL)
def init_db() -> None:
    with db() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute("""CREATE TABLE IF NOT EXISTS wiki_chunks (id BIGSERIAL PRIMARY KEY,
            title TEXT NOT NULL, source_url TEXT, chunk_index INTEGER NOT NULL, content TEXT NOT NULL,
            embedding vector(384) NOT NULL, created_at TIMESTAMPTZ DEFAULT now())""")
        conn.execute("CREATE INDEX IF NOT EXISTS wiki_chunks_embedding_idx ON wiki_chunks USING hnsw (embedding vector_cosine_ops)")
@asynccontextmanager
async def lifespan(_: FastAPI):
    try: init_db()
    except Exception as exc: print(f"Database initialization skipped: {exc}")
    yield
app = FastAPI(title="Wikipedia Knowledge Assistant", lifespan=lifespan)
@app.get("/")
async def root(): return {"message": "Wikipedia RAG API", "docs": "/docs"}
@app.get("/health")
async def health() -> dict[str, Any]:
    try:
        with db() as conn: count = conn.execute("SELECT count(*) FROM wiki_chunks").fetchone()[0]
        return {"status": "ok", "database": "connected", "chunks": count, "embedding_model": EMBEDDING_MODEL}
    except Exception as exc: return {"status": "degraded", "database": "unavailable", "detail": str(exc)}
@app.post("/ingest")
async def ingest(request: IngestRequest) -> dict[str, Any]:
    started = time.perf_counter(); parts = chunks(request.text)
    vectors = embedding_model().encode(parts, normalize_embeddings=True).tolist()
    with db() as conn:
        conn.execute("DELETE FROM wiki_chunks WHERE title = %s", (request.title,))
        for index, (content, vector) in enumerate(zip(parts, vectors)):
            conn.execute("INSERT INTO wiki_chunks (title, source_url, chunk_index, content, embedding) VALUES (%s, %s, %s, %s, %s)", (request.title, request.source_url, index, content, vector))
    return {"title": request.title, "chunks_created": len(parts), "embedding_dimensions": len(vectors[0]), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
@app.post("/ingest/wikipedia/{title}")
async def ingest_wikipedia(title: str) -> dict[str, Any]:
    try:
        import json; url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + quote(title.replace(" ", "_"))
        with urlopen(Request(url, headers={"User-Agent": "Wikipedia-Knowledge-Assistant/0.1"}), timeout=15) as response: page = json.load(response)
    except Exception as exc: raise HTTPException(status_code=502, detail=f"Wikipedia request failed: {exc}") from exc
    return await ingest(IngestRequest(title=page["title"], text=page.get("extract", ""), source_url=page.get("content_urls", {}).get("desktop", {}).get("page")))
@app.post("/ask")
async def ask(request: AskRequest) -> dict[str, Any]:
    started = time.perf_counter(); vector = embedding_model().encode(request.question, normalize_embeddings=True).tolist()
    with db() as conn:
        rows = conn.execute("""SELECT title, source_url, chunk_index, content, 1 - (embedding <=> %s::vector) AS score
            FROM wiki_chunks ORDER BY embedding <=> %s::vector LIMIT %s""", (vector, vector, request.top_k)).fetchall()
    sources = [{"title": r[0], "source_url": r[1], "chunk_index": r[2], "content": r[3], "score": round(float(r[4]), 4)} for r in rows]
    context = "\n\n".join(f"[{i + 1}] {item['content']}" for i, item in enumerate(sources))
    return {"question": request.question, "answer": "Generation is intentionally left visible: use the context below with your LLM.", "context": context, "sources": sources, "debug": {"retrieved": len(sources), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}}
