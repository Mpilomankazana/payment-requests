import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

VALID = {
    "requesterName": "Lerato Dlamini",
    "amount": 4500.00,
    "description": "Printing of A1 posters - supplier invoice INV-2231",
}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def use_test_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = use_test_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def create(client, **changes):
    return client.post("/payment-requests", json={**VALID, **changes})


def test_create_returns_201_and_pending(client):
    response = create(client)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["requesterName"] == "Lerato Dlamini"
    assert body["amount"] == 4500.00
    assert body["status"] == "Pending"
    assert body["rejectionReason"] is None
    assert body["createdAt"].endswith("Z")


@pytest.mark.parametrize("amount", [0, -1, -4500.50])
def test_amount_must_be_more_than_zero(client, amount):
    response = create(client, amount=amount)
    assert response.status_code == 400
    assert "amount" in response.json()["detail"][0]
    assert client.get("/payment-requests").json() == []


def test_missing_or_blank_fields_return_400(client):
    assert client.post("/payment-requests", json={}).status_code == 400
    assert create(client, requesterName="   ").status_code == 400
    assert create(client, description="").status_code == 400
    assert create(client, amount="abc").status_code == 400


def test_client_cannot_set_the_status(client):
    assert create(client, status="Approved").status_code == 400


def test_invalid_json_returns_400_not_a_crash(client):
    response = client.post(
        "/payment-requests",
        content="{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_get_one_and_404_when_missing(client):
    created = create(client).json()
    assert client.get(f"/payment-requests/{created['id']}").json() == created
    assert client.get("/payment-requests/999").status_code == 404


def test_list_and_filter_by_status(client):
    first = create(client).json()
    second = create(client).json()
    third = create(client).json()
    client.post(f"/payment-requests/{first['id']}/approve")
    client.post(f"/payment-requests/{second['id']}/reject", json={"reason": "No invoice"})

    assert len(client.get("/payment-requests").json()) == 3

    def ids(status):
        response = client.get("/payment-requests", params={"status": status})
        return [item["id"] for item in response.json()]

    assert ids("Pending") == [third["id"]]
    assert ids("Approved") == [first["id"]]
    assert ids("Rejected") == [second["id"]]


def test_unknown_status_filter_returns_400(client):
    assert client.get("/payment-requests", params={"status": "Banana"}).status_code == 400


def test_approve_a_pending_request(client):
    request_id = create(client).json()["id"]
    response = client.post(f"/payment-requests/{request_id}/approve")
    assert response.status_code == 200
    assert response.json()["status"] == "Approved"


def test_a_request_cannot_be_approved_twice(client):
    request_id = create(client).json()["id"]
    assert client.post(f"/payment-requests/{request_id}/approve").status_code == 200

    second = client.post(f"/payment-requests/{request_id}/approve")
    assert second.status_code == 409
    assert "already Approved" in second.json()["detail"]


def test_approve_unknown_request_returns_404(client):
    assert client.post("/payment-requests/999/approve").status_code == 404


def test_reject_stores_the_reason(client):
    request_id = create(client).json()["id"]
    response = client.post(
        f"/payment-requests/{request_id}/reject", json={"reason": "Invoice does not match"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Rejected"
    assert response.json()["rejectionReason"] == "Invoice does not match"


@pytest.mark.parametrize("body", [None, {}, {"reason": ""}, {"reason": "   "}])
def test_rejecting_requires_a_reason(client, body):
    request_id = create(client).json()["id"]
    response = client.post(f"/payment-requests/{request_id}/reject", json=body)
    assert response.status_code == 400

    assert client.get(f"/payment-requests/{request_id}").json()["status"] == "Pending"


def test_only_pending_requests_can_be_rejected(client):
    request_id = create(client).json()["id"]
    client.post(f"/payment-requests/{request_id}/approve")
    response = client.post(f"/payment-requests/{request_id}/reject", json={"reason": "Too late"})
    assert response.status_code == 409

    assert client.get(f"/payment-requests/{request_id}").json()["status"] == "Approved"


def test_a_rejected_request_cannot_be_approved(client):
    request_id = create(client).json()["id"]
    client.post(f"/payment-requests/{request_id}/reject", json={"reason": "No budget"})
    assert client.post(f"/payment-requests/{request_id}/approve").status_code == 409

    assert client.get(f"/payment-requests/{request_id}").json()["rejectionReason"] == "No budget"
