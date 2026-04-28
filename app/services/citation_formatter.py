from dataclasses import dataclass
import re

from app.models.chunk import Chunk
from app.utils.text import compact_snippet

CITATION_RE = re.compile(r"\[(S\d+)\]")


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: Chunk
    score: float
    source: str = "vector"


def citation_label(index: int) -> str:
    return f"S{index + 1}"


def build_source_context(results: list[RetrievedChunk], max_chars: int | None = None) -> tuple[str, list[dict]]:
    blocks: list[str] = []
    citations: list[dict] = []
    used_chars = 0

    for idx, result in enumerate(results):
        chunk = result.chunk
        label = citation_label(idx)
        filename = chunk.document.filename if chunk.document else "unknown"
        page = _format_page_range(chunk.page_start, chunk.page_end)
        block = f"[{label}] {filename}{page}\n{chunk.text}"
        if max_chars is not None and blocks and used_chars + len(block) > max_chars:
            break
        used_chars += len(block)
        blocks.append(block)
        citations.append(
            {
                "label": label,
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "filename": filename,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "score": round(result.score, 4),
                "snippet": compact_snippet(chunk.text),
            }
        )

    return "\n\n---\n\n".join(blocks), citations


def select_citations_for_answer(answer: str, citations: list[dict]) -> tuple[str, list[dict]]:
    valid_by_label = {citation["label"]: citation for citation in citations}
    labels_in_answer = [label for label in CITATION_RE.findall(answer) if label in valid_by_label]

    if labels_in_answer:
        unique_labels = list(dict.fromkeys(labels_in_answer))
        return answer, [valid_by_label[label] for label in unique_labels]

    if _is_no_answer(answer) or not citations:
        return answer, []

    return answer, []


def answer_has_strong_citation_support(answer: str, citations: list[dict], min_score: float) -> bool:
    if _is_no_answer(answer):
        return True
    valid_by_label = {citation["label"]: citation for citation in citations if float(citation.get("score", 0.0)) >= min_score}
    if not valid_by_label:
        return False

    for claim in _extract_claims(answer):
        labels = CITATION_RE.findall(claim)
        if not labels:
            return False
        if any(label not in valid_by_label for label in labels):
            return False
    return True


def _is_no_answer(answer: str) -> bool:
    normalized = answer.lower()
    return "could not find" in normalized or "not found" in normalized or "not in the uploaded documents" in normalized


def _extract_claims(answer: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _format_page_range(page_start: int | None, page_end: int | None) -> str:
    if page_start is None:
        return ""
    if page_end is None or page_end == page_start:
        return f", page {page_start}"
    return f", pages {page_start}-{page_end}"
