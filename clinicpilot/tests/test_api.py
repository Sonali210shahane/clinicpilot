import pytest

from app import create_app
from clinicpilot.ai import GeminiClient


@pytest.fixture
def client(tmp_path):
    app = create_app(client=GeminiClient(api_key=""), queue_path=tmp_path / "queue.json")
    return app.test_client()


def test_home_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"ClinicPilot" in res.data


def test_config(client):
    data = client.get("/api/config").get_json()
    assert data["ai_enabled"] is False
    assert len(data["red_flags"]) == 9
    assert set(data["levels"]) == {"emergency", "urgent", "routine", "telehealth", "selfcare"}


def test_triage(client):
    res = client.post("/api/triage", json={"name": "Mia", "age": 4, "symptoms": "Ear pain and fever 38.9",
                                           "duration": "1to3", "severity": 6})
    assert res.status_code == 200
    result = res.get_json()["result"]
    assert result["level"] == "urgent"
    assert result["title"] == "See a GP today"


def test_triage_rejects_bad_input(client):
    res = client.post("/api/triage", json={"symptoms": "cough"})
    assert res.status_code == 400
    assert "Age" in res.get_json()["error"]


def test_queue_starts_with_examples(client):
    queue = client.get("/api/queue").get_json()
    assert len(queue) == 5
    assert all(e["example"] for e in queue)


def test_queue_add_sort_and_remove(client):
    res = client.post("/api/queue", json={"name": "Graham", "age": 61, "request_type": "new", "severity": 7,
                                          "level": "emergency", "appointment": "none", "summary": "chest pain"})
    assert res.status_code == 201
    entry_id = res.get_json()["id"]

    queue = client.get("/api/queue").get_json()
    assert queue[0]["id"] == entry_id

    assert client.delete(f"/api/queue/{entry_id}").status_code == 204
    assert client.delete(f"/api/queue/{entry_id}").status_code == 404


def test_queue_rejects_invalid_level(client):
    res = client.post("/api/queue", json={"level": "panic", "appointment": "none"})
    assert res.status_code == 400


def test_queue_clear_and_reload(client):
    assert client.delete("/api/queue").status_code == 204
    assert client.get("/api/queue").get_json() == []
    assert len(client.post("/api/queue/examples").get_json()) == 5


def test_queue_csv(client):
    res = client.get("/api/queue.csv")
    assert res.mimetype == "text/csv"
    lines = res.data.decode().strip().splitlines()
    assert lines[0].startswith("priority,received,patient")
    assert len(lines) == 6


def test_chat(client):
    data = client.post("/api/chat", json={"message": "Do you bulk bill kids?"}).get_json()
    assert "bulk billed" in data["answer"]


def test_chat_emergency(client):
    data = client.post("/api/chat", json={"message": "My dad has crushing chest pain"}).get_json()
    assert "000" in data["answer"]
    assert data["alert"] is True


def test_chat_needs_message(client):
    assert client.post("/api/chat", json={"message": " "}).status_code == 400
