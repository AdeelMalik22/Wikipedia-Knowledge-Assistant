from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
from app.core.config import settings

_model: Any = None

def get_model() -> Any:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
    return _model

def embed(texts: list[str] | str) -> list[list[float]] | list[float]:
    return get_model().encode(texts, normalize_embeddings=True).tolist()
