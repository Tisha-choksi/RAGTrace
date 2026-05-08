from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


SENSITIVE_TERMS = {
    "password",
    "secret",
    "api key",
    "token",
    "salary",
    "ssn",
    "aadhaar",
    "credit card",
    "bank",
    "confidential",
}


def detect_alerts(
    db: Session,
    user_id: str,
    query: str,
    chunks: list[dict],
    timestamp: datetime,
) -> list[str]:
    alerts: list[str] = []
    query_lower = query.lower()

    matched_terms = [term for term in SENSITIVE_TERMS if term in query_lower]
    if matched_terms:
        alerts.append(f"Sensitive query terms detected: {', '.join(matched_terms)}")

    if not chunks:
        alerts.append("No retrieved chunks were available for this answer.")

    recent_logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .where(AuditLog.timestamp >= timestamp - timedelta(minutes=5))
    ).all()
    if len(recent_logs) >= 10:
        alerts.append("High query volume from this user in the last 5 minutes.")

    low_scores = [chunk.get("score") for chunk in chunks if isinstance(chunk.get("score"), int | float)]
    if low_scores and max(low_scores) < 0.25:
        alerts.append("Retrieved context has low similarity scores.")

    return alerts
