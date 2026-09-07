# Wikipedia Knowledge Assistant

An inspectable FastAPI RAG system for Wikipedia content. It uses PostgreSQL with
pgvector for vector search and `sentence-transformers` for embeddings.

## Architecture

```text
Wikipedia API
     |
     v
Batch importer ----> FastAPI /ingest ----> PostgreSQL + pgvector
     |                         |
     |                         +--> wiki_documents.pdf_data
     +--> PDF sent as base64

Question ----> FastAPI /ask ----> embedding ----> cosine similarity search
                                      |
                                      +--> ranked sources and context
```

The `/ask` endpoint currently returns the retrieved context and ranked sources.
Generation is intentionally left visible so retrieval can be reviewed before an
LLM is connected.

## Requirements

- Python 3.11+
- PostgreSQL 14+
- PostgreSQL `pgvector` extension
- Internet access for Wikipedia and the embedding model

The application does not require Docker.

## PostgreSQL setup

Create a database and user matching your local configuration, or use your own
credentials and set `DATABASE_URL` accordingly:

```bash
export DATABASE_URL="postgresql://myuser:123@localhost:5432/wpr"
```

Install pgvector for your PostgreSQL version. If your Ubuntu repositories do not
contain a pgvector package, build it from source:

```bash
sudo apt install -y build-essential git postgresql-server-dev-14
cd /tmp
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
sudo systemctl restart postgresql
```

## Install and migrate

```bash
cd Wikipedia-Knowledge-Assistant
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://myuser:123@localhost:5432/wpr"
python scripts/migrate.py
```

The migration creates:

- `wiki_documents`: article metadata and PDF bytes in `pdf_data`
- `wiki_chunks`: chunk text and 384-dimensional embeddings
- an HNSW cosine-similarity index for vector retrieval

## Run the API

```bash
uvicorn main:app --reload
```

Open the interactive API documentation at <http://127.0.0.1:8000/docs>.

Check the database connection:

```bash
curl http://127.0.0.1:8000/health
```

## Import Wikipedia articles

Run a small test first:

```bash
python scripts/ingest_random_wikipedia.py --count 5
```

Import 1,000 random articles:

```bash
python scripts/ingest_random_wikipedia.py --count 1000
```

The importer fetches Wikipedia summaries, creates PDFs in memory, sends them to
the FastAPI `/ingest` endpoint, and stores the PDF bytes in PostgreSQL. It does
not write PDFs into the repository. Progress and failures are printed to the
terminal.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check PostgreSQL and document count |
| `POST` | `/ingest` | Ingest text, embeddings, and optional PDF data |
| `POST` | `/ingest/wikipedia/{title}` | Fetch and ingest one Wikipedia summary |
| `POST` | `/ask` | Retrieve ranked context from stored chunks |

Example retrieval request:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is Python used for?","top_k":3}'
```

## Project structure

```text
app/
├── api/routes/       FastAPI route handlers
├── core/             settings and database connection
├── schemas/          request validation models
├── services/         chunking, embeddings, ingestion, retrieval
└── main.py           FastAPI application
migrations/           SQL schema migrations
scripts/              migration and batch-import scripts
main.py               uvicorn compatibility entrypoint
```
