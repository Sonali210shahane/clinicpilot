import json

import pytest
import requests

from clinicpilot.ai import AIError, GeminiClient, parse_triage_answer, triage_with_ai
from clinicpilot.clinic import answer_question
from clinicpilot.rules import Intake


class FakeClient:
    """Stands in for Gemini so tests don't need a key or the internet."""

    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = []
        self.model = "fake"

    @property
    def enabled(self):
        return True

    def generate(self, system, contents, json_mode=False):
        self.calls.append({"system": system, "contents": contents, "json_mode": json_mode})
        if self.error:
            raise AIError(self.error)
        return self.reply


def answer(**kwargs):
    data = {"urgency": "routine", "appointment": "standard15", "reasons": ["test"],
            "patient_message": "Please book a GP.", "reception_summary": "summary", "escalated": False}
    data.update(kwargs)
    return json.dumps(data)


def intake(**kwargs):
    data = {"age": 30, "symptoms": "cough", "duration": "1to3", "severity": 3}
    data.update(kwargs)
    return Intake.from_dict(data)


def test_ai_can_escalate():
    client = FakeClient(answer(urgency="routine", reasons=["Sore throat may need a check"]))
    result = triage_with_ai(intake(symptoms="Runny nose and sore throat", severity=2), client)
    assert result.level == "routine"
    assert result.escalated
    assert result.source == "ai"
    assert any(r["source"] == "ai" for r in result.reasons)
    assert client.calls[0]["json_mode"]


def test_ai_cannot_downgrade():
    client = FakeClient(answer(urgency="selfcare", appointment="none"))
    result = triage_with_ai(intake(age=4, symptoms="Ear pain and fever 38.9", severity=6), client)
    assert result.level == "urgent"
    assert result.appointment == "standard15"
    assert any(r["source"] == "guard" for r in result.reasons)


def test_ai_cannot_remove_an_emergency():
    client = FakeClient(answer(urgency="routine", patient_message="Book a GP next week."))
    result = triage_with_ai(intake(symptoms="Crushing chest pain", severity=8), client)
    assert result.level == "emergency"
    assert result.appointment == "none"
    assert "000" in result.message


def test_crisis_message_always_has_lifeline():
    client = FakeClient(answer(urgency="emergency", appointment="none", patient_message="Please call 000."))
    result = triage_with_ai(intake(symptoms="I want to end it all", severity=8), client)
    assert "13 11 14" in result.message


def test_invalid_ai_answer_falls_back_to_rules():
    client = FakeClient("Sorry, I can't help with that.")
    result = triage_with_ai(intake(age=4, symptoms="Ear pain and fever", severity=6), client)
    assert result.level == "urgent"
    assert result.source == "rules"
    assert "AI unavailable" in result.notice


def test_api_error_falls_back_to_rules():
    result = triage_with_ai(intake(), FakeClient(error="Gemini returned 429"))
    assert result.source == "rules"
    assert "429" in result.notice


def test_no_client_uses_rules_only():
    assert triage_with_ai(intake(), None).source == "rules"


def test_ai_input_does_not_include_patient_name():
    client = FakeClient(answer())
    triage_with_ai(intake(name="Jane Citizen"), client)
    assert "Jane Citizen" not in json.dumps(client.calls[0]["contents"])


@pytest.mark.parametrize("text", ["not json", '{"urgency": "very bad"}', "{broken"])
def test_parse_rejects_bad_answers(text):
    with pytest.raises(AIError):
        parse_triage_answer(text)


def test_parse_accepts_json_inside_text():
    parsed = parse_triage_answer('Here you go: {"urgency": "urgent", "appointment": "long30"}')
    assert parsed["urgency"] == "urgent"


def test_gemini_client_disabled_without_key():
    client = GeminiClient(api_key="")
    assert not client.enabled
    with pytest.raises(AIError):
        client.generate("system", [])


def test_gemini_client_network_error(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError()

    monkeypatch.setattr(requests, "post", fail)
    with pytest.raises(AIError, match="Could not reach Gemini"):
        GeminiClient(api_key="key").generate("system", [])


def test_gemini_client_reads_text(monkeypatch):
    class Response:
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}

    monkeypatch.setattr(requests, "post", lambda *a, **k: Response())
    assert GeminiClient(api_key="key").generate("system", []) == "hello"


def test_chat_uses_ai_when_available():
    client = FakeClient("We're open every day from 7am.")
    reply = answer_question("When are you open?", [], client)
    assert reply["source"] == "Gemini"
    assert "CLINIC INFORMATION" in client.calls[0]["system"]


def test_chat_falls_back_to_faq():
    reply = answer_question("When are you open?", [], FakeClient(error="timeout"))
    assert reply["source"] == "Clinic FAQ"
    assert "7 days a week" in reply["answer"]
