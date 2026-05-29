import re


PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("AADHAAR", re.compile(r"(?<!\d)\d{4}[-\s]?\d{4}[-\s]?\d{4}(?!\d)")),
    (
        "CREDIT_CARD",
        re.compile(
            r"(?<!\d)"
            r"(?:"
            r"4\d{3}(?:[-\s]\d{4}){3}"            # Visa 16-digit
            r"|5[1-5]\d{2}(?:[-\s]\d{4}){3}"      # Mastercard 16-digit
            r"|3[47]\d{2}[-\s]\d{6}[-\s]\d{5}"    # Amex 15-digit
            r"|6(?:011|5\d{2})(?:[-\s]\d{4}){3}"  # Discover 16-digit
            r")"
            r"(?!\d)"
        ),
    ),
    (
        "PHONE",
        re.compile(
            r"(?:"
            r"\+\d{1,3}[-.\s]\(?\d{1,4}\)?[-.\s]\d{1,9}[-.\s]\d{4}"  # +country-area-number
            r"|\(\d{3}\)[-.\s]\d{3}[-.\s]\d{4}"                         # (xxx) xxx-xxxx
            r"|\b[6-9]\d{9}\b"                                           # Indian mobile (10 digits, 6-9 prefix)
            r")"
        ),
    ),
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
