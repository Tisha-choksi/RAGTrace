import re


PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3,5}\)?[-.\s]?)?\d{3,5}[-.\s]?\d{4}(?!\d)")),
    ("AADHAAR", re.compile(r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)")),
    ("CREDIT_CARD", re.compile(r"(?<!\d)(?:\d[ -]*?){13,19}(?!\d)")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]


def mask_pii(text: str) -> str:
    masked = text
    for label, pattern in PII_PATTERNS:
        masked = pattern.sub(f"[{label}]", masked)
    return masked


def mask_chunks(chunks: list[dict]) -> list[dict]:
    masked_chunks = []
    for chunk in chunks:
        item = dict(chunk)
        if isinstance(item.get("text"), str):
            item["text"] = mask_pii(item["text"])
        masked_chunks.append(item)
    return masked_chunks

