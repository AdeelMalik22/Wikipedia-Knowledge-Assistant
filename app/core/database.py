import psycopg
from app.core.config import settings

def get_connection() -> psycopg.Connection:
    return psycopg.connect(settings.database_url)

def init_db() -> None:
    with get_connection() as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.execute("""CREATE TABLE IF NOT EXISTS wiki_documents (
            title TEXT PRIMARY KEY, source_url TEXT, pdf_data BYTEA,
            created_at TIMESTAMPTZ DEFAULT now())""")
        connection.execute("""CREATE TABLE IF NOT EXISTS wiki_chunks (
            id BIGSERIAL PRIMARY KEY, title TEXT NOT NULL, source_url TEXT,
            chunk_index INTEGER NOT NULL, content TEXT NOT NULL,
            embedding vector(384) NOT NULL, created_at TIMESTAMPTZ DEFAULT now())""")
        connection.execute("CREATE INDEX IF NOT EXISTS wiki_chunks_embedding_idx ON wiki_chunks USING hnsw (embedding vector_cosine_ops)")
