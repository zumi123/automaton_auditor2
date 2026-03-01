"""Forensic tools for document analysis - DocAnalyst capabilities."""

from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader


def ingest_pdf(path: str) -> tuple[List[str], Optional[str]]:
    """
    Parse PDF into text chunks for RAG-lite querying.
    Returns (chunks, error_message). Chunks are ~500 char overlapping segments.
    """
    p = Path(path)
    if not p.exists():
        return ([], f"File not found: {path}")
    if p.suffix.lower() != ".pdf":
        return ([], f"Not a PDF file: {path}")

    try:
        reader = PdfReader(str(p))
        full_text_parts: List[str] = []
        for page in reader.pages:
            try:
                text = page.extract_text()
                if text:
                    full_text_parts.append(text)
            except Exception:
                pass

        full_text = "\n\n".join(full_text_parts)
        if not full_text.strip():
            return ([], "No text could be extracted from PDF")

        # Chunk with overlap for context
        chunk_size = 500
        overlap = 100
        chunks: List[str] = []
        start = 0
        while start < len(full_text):
            end = start + chunk_size
            chunk = full_text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap
            if overlap >= end - start:
                break

        return (chunks, None)
    except Exception as e:
        return ([], str(e))


def query_pdf_chunks(chunks: List[str], query: str) -> List[str]:
    """
    Simple RAG-lite: return chunks that contain query keywords.
    For production, use embeddings + similarity search.
    """
    if not chunks:
        return []
    query_lower = query.lower()
    keywords = [w for w in query_lower.split() if len(w) > 2]
    if not keywords:
        return chunks[:3]

    scored: List[tuple[float, str]] = []
    for chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(1 for k in keywords if k in chunk_lower)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: -x[0])
    return [c for _, c in scored[:5]]


def extract_images_from_pdf(path: str) -> List[tuple[int, bytes]]:
    """
    Extract images from PDF pages for VisionInspector.
    Returns list of (page_index, image_bytes).
    """
    p = Path(path)
    if not p.exists():
        return []
    try:
        reader = PdfReader(str(p))
        images: List[tuple[int, bytes]] = []
        for i, page in enumerate(reader.pages):
            try:
                img_dict = getattr(page, "images", None)
                if not img_dict:
                    continue
                keys = list(img_dict.keys()) if hasattr(img_dict, "keys") else []
                for name in keys:
                    try:
                        img_obj = img_dict[name]
                        if hasattr(img_obj, "image") and hasattr(img_obj.image, "save"):
                            from io import BytesIO
                            buf = BytesIO()
                            img_obj.image.save(buf, format="PNG")
                            images.append((i, buf.getvalue()))
                        elif hasattr(img_obj, "get_data"):
                            data = img_obj.get_data()
                            if data:
                                images.append((i, data))
                    except Exception:
                        pass
            except Exception:
                pass
        return images
    except Exception:
        return []
