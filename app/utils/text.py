import re


WHITESPACE_RE = re.compile(r"[ \t]+")
LINEBREAK_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = WHITESPACE_RE.sub(" ", text)
    text = LINEBREAK_RE.sub("\n\n", text)
    return text.strip()


def count_tokens_approx(text: str) -> int:
    # A conservative approximation good enough for chunk boundaries without tiktoken.
    return max(1, len(text.split()))


def compact_snippet(text: str, max_chars: int = 360) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."

