from typing import List


def simple_chunk(text: str, max_size: int = 1000, overlap: int = 200) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_size, length)
        chunks.append(text[start:end])
        if end == length:
            break
        start = max(0, end - overlap)
    return chunks
