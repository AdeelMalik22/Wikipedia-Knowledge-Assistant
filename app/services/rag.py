import base64
import logging
import time
from typing import Any
from app.core.database import get_connection
from app.services.chunking import split_into_chunks
from app.services.embedding import embed

logger = logging.getLogger(__name__)

def ingest(title: str, text: str, source_url: str | None, pdf_base64: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        parts = split_into_chunks(text)
        vectors = embed(parts)
        pdf_data = base64.b64decode(pdf_base64) if pdf_base64 else None
        with get_connection() as connection:
            connection.execute("""INSERT INTO wiki_documents (title, source_url, pdf_data)
                VALUES (%s, %s, %s)
                ON CONFLICT (title) DO UPDATE SET source_url = EXCLUDED.source_url, pdf_data = EXCLUDED.pdf_data""", (title, source_url, pdf_data))
            connection.execute("DELETE FROM wiki_chunks WHERE title = %s", (title,))
            for index, (content, vector) in enumerate(zip(parts, vectors)):
                connection.execute("INSERT INTO wiki_chunks (title, source_url, chunk_index, content, embedding) VALUES (%s, %s, %s, %s, %s)", (title, source_url, index, content, vector))
        return {"title": title, "chunks_created": len(parts), "embedding_dimensions": len(vectors[0]), "pdf_stored": pdf_data is not None, "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
    except Exception as exc:
        logger.exception("Document ingestion failed for title=%r", title)
        raise RuntimeError(f"Document ingestion failed for '{title}': {exc}") from exc

def retrieve(question: str, top_k: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        vector = embed(question)
        with get_connection() as connection:
            rows = connection.execute("""SELECT title, source_url, chunk_index, content, 1 - (embedding <=> %s::vector) AS score
                FROM wiki_chunks ORDER BY embedding <=> %s::vector LIMIT %s""", (vector, vector, top_k)).fetchall()
        sources = [{"title": r[0], "source_url": r[1], "chunk_index": r[2], "content": r[3], "score": round(float(r[4]), 4)} for r in rows]
        return {"sources": sources, "context": "\n\n".join(f"[{i + 1}] {item['content']}" for i, item in enumerate(sources)), "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)}
    except Exception as exc:
        logger.exception("Retrieval failed for question=%r", question)
        raise RuntimeError(f"Retrieval failed: {exc}") from exc
