from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_home_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "shop" in response.text


def test_empty_question_is_rejected():
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
