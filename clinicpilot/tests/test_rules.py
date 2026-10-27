import pytest

from clinicpilot.rules import Intake, more_urgent, triage


def make(**kwargs):
    data = {"age": 30, "symptoms": "", "duration": "1to3", "severity": 3, "request_type": "new"}
    data.update(kwargs)
    return Intake.from_dict(data)


@pytest.mark.parametrize("fields, level, appointment", [
    (dict(age=61, symptoms="Tightness across my chest since an hour ago, goes down my left arm",
          severity=7, duration="lt24"), "emergency", "none"),
    (dict(age=70, symptoms="My face is drooping on one side and my speech is slurred", severity=6),
     "emergency", "none"),
    (dict(age=27, symptoms="Throat is swelling and lips puffy after eating prawns", severity=8),
     "emergency", "none"),
    (dict(age=4, symptoms="Ear pain and fever 38.9, not eating", severity=6), "urgent", "standard15"),
    (dict(age=0, symptoms="Temperature 38.2, unsettled", severity=4), "urgent", "standard15"),
    (dict(age=30, symptoms="Cramping low in my tummy", severity=4, pregnant=True), "urgent", "standard15"),
    (dict(age=80, symptoms="Feeling dizzy and tired", severity=5), "urgent", "standard15"),
    (dict(age=40, symptoms="Mild back ache", severity=6, duration="lt24"), "urgent", "standard15"),
    (dict(age=68, symptoms="Need my blood pressure tablets", severity=0, request_type="script",
          duration="na"), "telehealth", "telehealth15"),
    (dict(age=50, symptoms="Review of rash, improving", severity=2, request_type="followup"),
     "telehealth", "telehealth15"),
    (dict(age=29, symptoms="Runny nose and a sore throat", severity=2), "selfcare", "pharmacist"),
    (dict(age=34, symptoms="Feeling anxious and can't sleep", severity=5, duration="gt7"), "routine", "long30"),
    (dict(age=52, symptoms="Flu shot", severity=0, request_type="vaccine", duration="na"), "routine", "nurse"),
    (dict(age=64, symptoms="Diabetes, new numbness in feet", severity=4, duration="gt7"), "routine", "long30"),
])
def test_routing(fields, level, appointment):
    result = triage(make(**fields))
    assert result.level == level
    assert result.appointment == appointment
    assert result.reasons


def test_self_harm_is_a_crisis():
    result = triage(make(symptoms="I want to end it all", severity=8))
    assert result.level == "emergency"
    assert result.crisis
    assert "13 11 14" in result.message


def test_ticked_flag_counts_even_without_words():
    result = triage(make(symptoms="", flags=["breath"]))
    assert result.level == "emergency"
    assert "ticked" in result.reasons[0]["text"]


def test_cold_symptoms_in_risk_groups_are_not_self_care():
    assert triage(make(age=1, symptoms="Runny nose", severity=2)).level != "selfcare"
    assert triage(make(age=80, symptoms="Runny nose", severity=2)).level != "selfcare"
    assert triage(make(symptoms="Runny nose", severity=2, chronic=True)).level != "selfcare"


def test_admin_request_with_high_severity_goes_in_person():
    result = triage(make(symptoms="Need a certificate, still quite sick", request_type="certificate", severity=6))
    assert result.level == "routine"


def test_summary_contains_key_details():
    result = triage(make(age=4, symptoms="Ear pain and fever", severity=6))
    assert result.summary.startswith("4y.")
    assert "sev 6/10" in result.summary
    assert "SAME-DAY" in result.summary


def test_known_limitation_negation_still_flags():
    assert triage(make(symptoms="No chest pain, just a cough")).level == "emergency"


@pytest.mark.parametrize("data, message", [
    ({"symptoms": "cough"}, "Age"),
    ({"age": "abc", "symptoms": "cough"}, "Age"),
    ({"age": 150, "symptoms": "cough"}, "between 0 and 120"),
    ({"age": 30, "symptoms": ""}, "Describe"),
    ({"age": 30, "symptoms": "cough", "request_type": "pizza"}, "request type"),
])
def test_invalid_input(data, message):
    with pytest.raises(ValueError, match=message):
        Intake.from_dict(data)


def test_severity_is_clamped():
    assert Intake.from_dict({"age": 30, "symptoms": "cough", "severity": 15}).severity == 10


def test_more_urgent():
    assert more_urgent("routine", "urgent") == "urgent"
    assert more_urgent("emergency", "selfcare") == "emergency"
