from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import APPROVED, PENDING, REJECTED, STATUSES, PaymentRequest
from .schemas import CreateRequest, RejectRequest

router = APIRouter(prefix="/payment-requests", tags=["payment-requests"])


def to_json(item):
    return {
        "id": item.id,
        "requesterName": item.requester_name,
        "amount": item.amount_cents / 100,
        "description": item.description,
        "status": item.status,
        "createdAt": item.created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rejectionReason": item.rejection_reason,
    }


def get_or_404(db, request_id):
    item = db.get(PaymentRequest, request_id)
    if item is None:
        raise HTTPException(404, f"Payment request {request_id} was not found.")
    return item


def change_status(db, item, new_status, reason=None):
    # Business rule: only Pending requests can be approved or rejected.
    if item.status != PENDING:
        raise HTTPException(
            409,
            f"Only Pending requests can be approved or rejected. "
            f"Request {item.id} is already {item.status}.",
        )
    item.status = new_status
    item.rejection_reason = reason
    db.commit()
    return to_json(item)


@router.post("", status_code=201)
def create_request(body: CreateRequest, db: Session = Depends(get_db)):
    item = PaymentRequest(
        requester_name=body.requesterName,
        amount_cents=int(body.amount * 100),
        description=body.description,
    )
    db.add(item)
    db.commit()
    return to_json(item)


@router.get("")
def list_requests(status: str | None = None, db: Session = Depends(get_db)):
    query = select(PaymentRequest).order_by(PaymentRequest.id)
    if status is not None:
        status = status.strip().capitalize()
        if status not in STATUSES:
            raise HTTPException(
                400, f"Invalid status. Use one of: {', '.join(STATUSES)}."
            )
        query = query.where(PaymentRequest.status == status)
    return [to_json(item) for item in db.scalars(query)]


@router.get("/{request_id}")
def get_request(request_id: int, db: Session = Depends(get_db)):
    return to_json(get_or_404(db, request_id))


@router.post("/{request_id}/approve")
def approve_request(request_id: int, db: Session = Depends(get_db)):
    item = get_or_404(db, request_id)
    return change_status(db, item, APPROVED)


@router.post("/{request_id}/reject")
def reject_request(request_id: int, body: RejectRequest, db: Session = Depends(get_db)):
    item = get_or_404(db, request_id)
    return change_status(db, item, REJECTED, reason=body.reason)
