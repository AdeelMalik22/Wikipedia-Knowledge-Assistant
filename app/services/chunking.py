def split_into_chunks(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    words = text.split(); step = size - overlap
    return [part for start in range(0, len(words), step) if (part := " ".join(words[start:start + size]).strip())]
