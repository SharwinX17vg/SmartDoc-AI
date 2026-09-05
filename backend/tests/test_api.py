from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_rejects_non_pdf():
    response = client.post("/api/v1/documents", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400
