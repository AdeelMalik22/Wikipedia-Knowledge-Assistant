from sentence_transformers import SentenceTransformer
from app.core.config import settings

_model: SentenceTransformer | None = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model

def embed(texts: list[str] | str) -> list[list[float]] | list[float]:
    return get_model().encode(texts, normalize_embeddings=True).tolist()
