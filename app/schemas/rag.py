from pydantic import BaseModel, Field
from app.core.config import settings

class IngestRequest(BaseModel):
    title: str = Field(min_length=1)
    text: str = Field(min_length=20)
    source_url: str | None = None

class AskRequest(BaseModel):
    question: str = Field(min_length=3)
    top_k: int = Field(default=settings.top_k, ge=1, le=20)
