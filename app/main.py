from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes.health import router as health_router
from app.api.routes.rag import router as rag_router
from app.core.database import init_db

@asynccontextmanager
async def lifespan(_: FastAPI):
    try: init_db()
    except Exception as exc: print(f"Database initialization skipped: {exc}")
    yield

app = FastAPI(title="Wikipedia Knowledge Assistant", lifespan=lifespan)
app.include_router(health_router)
app.include_router(rag_router)

@app.get("/")
async def root(): return {"message": "Wikipedia RAG API", "docs": "/docs"}
