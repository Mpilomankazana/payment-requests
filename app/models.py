from datetime import datetime, timezone

from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

PENDING = "Pending"
APPROVED = "Approved"
REJECTED = "Rejected"
STATUSES = [PENDING, APPROVED, REJECTED]


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_name: Mapped[str]
    amount_cents: Mapped[int]  # 4500.00 is stored as 450000
    description: Mapped[str]
    status: Mapped[str] = mapped_column(default=PENDING)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    rejection_reason: Mapped[str | None] = mapped_column(default=None)
